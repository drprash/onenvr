import os
import schedule
import time
import threading
from datetime import datetime, timedelta
from config import load_config, setup_logging
from recorder import StreamRecorder
from video_manager import VideoManager
from web_interface import create_web_server
from config_watcher import ConfigWatcher
from discovery_scheduler import DiscoveryScheduler
import logging
import shutil

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

class NVRSystem:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing OneNVR system")
        self.config = load_config()
        self.recorders = {}
        self.video_manager = VideoManager(self.config['retention_days'])
        self.config_watcher = None
        self.web_app = None
        self._lock = threading.RLock()  # For thread-safe config updates
        self.discovery_scheduler = None

        self.setup_recorders()
        self.setup_schedules()
        self.setup_config_watcher()
        self.start_web_server()

    def setup_recorders(self):
        """Initialize recorders from current configuration."""
        with self._lock:
            self.logger.debug(f"Setting up recorders for {len(self.config['cameras'])} cameras")

            # Stop existing recorders not in new config
            current_names = {c['name'] for c in self.config['cameras']}
            for name in list(self.recorders.keys()):
                if name not in current_names:
                    self.logger.info(f"Removing recorder for deleted camera: {name}")
                    self.recorders[name].stop()
                    del self.recorders[name]

            # Start/update recorders
            for camera_config in self.config['cameras']:
                try:
                    camera_name = camera_config['name']

                    # If recorder exists, check if config changed
                    if camera_name in self.recorders:
                        existing = self.recorders[camera_name]
                        if (existing.rtsp_url != camera_config['rtsp_url'] or
                            existing.codec != camera_config['codec'] or
                            existing.interval != camera_config['interval']):
                            self.logger.info(f"Config changed for {camera_name}, restarting recorder")
                            existing.stop()
                            self.recorders[camera_name] = StreamRecorder(camera_config)
                            self.recorders[camera_name].start()
                    else:
                        # New camera — start immediately instead of waiting for health_check
                        self.recorders[camera_name] = StreamRecorder(camera_config)
                        self.recorders[camera_name].start()

                except ValueError as e:
                    self.logger.error(f"Invalid camera configuration: {str(e)}")
                    continue

            self.video_manager.set_recorders(self.recorders)
            self.video_manager.update_retention(self.config['retention_days'])
            self.logger.debug("All recorders setup complete")

    def setup_schedules(self):
        """Setup scheduled tasks based on current configuration."""
        self.logger.debug("Setting up scheduled tasks")

        # Clear existing schedules
        schedule.clear()

        # Concatenation schedule
        if self.config['concatenation']:
            schedule.every().day.at(self.config['concatenation_time']).do(self.concatenate_all_cameras)
            self.logger.info(f"Scheduled daily concatenation at {self.config['concatenation_time']}")

        # Cleanup schedule
        schedule.every().day.at(self.config['deletion_time']).do(
            self.video_manager.cleanup_old_recordings
        )
        self.logger.info(f"Scheduled daily cleanup at {self.config['deletion_time']}")

        # Health checks and maintenance
        schedule.every(2).minutes.do(self.health_check)
        schedule.every(5).minutes.do(self.disk_space_check)

        # Discovery rediscovery schedule
        disc_cfg = self.config.get('discovery')
        if disc_cfg and disc_cfg.get('enabled'):
            if self.discovery_scheduler is None:
                self.discovery_scheduler = DiscoveryScheduler(
                    config_ref=self.config,
                    lock=self._lock,
                    discovery_config=disc_cfg
                )
            schedule.every(disc_cfg['interval_minutes']).minutes.do(
                self.discovery_scheduler.run_rediscovery
            )
            self.logger.info(
                f"Scheduled discovery rediscovery every {disc_cfg['interval_minutes']} minutes"
            )
            # Warn if multicast may be unreachable in Docker
            import socket as _socket
            try:
                s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
                s.connect(('239.255.255.250', 3702))
                s.close()
            except OSError:
                self.logger.warning(
                    "Discovery enabled but multicast may be unreachable. "
                    "Run container with --network host or a macvlan network."
                )

        self.logger.debug("Schedule setup complete")

    def setup_config_watcher(self):
        """Initialize configuration file watcher for hot-reload."""
        config_path = '/config/config.yaml'
        self.config_watcher = ConfigWatcher(
            config_path=config_path,
            callback=self.reload_config,
            poll_interval=5
        )
        self.config_watcher.start()

    def reload_config(self):
        """Reload configuration and apply changes without restart."""
        self.logger.info("Reloading configuration...")

        try:
            with self._lock:
                # Load new configuration
                new_config = load_config()

                # Check what changed
                old_cameras = {c['name'] for c in self.config['cameras']}
                new_cameras = {c['name'] for c in new_config['cameras']}

                config_changed = (
                    old_cameras != new_cameras or
                    self.config.get('retention_days') != new_config.get('retention_days') or
                    self.config.get('concatenation') != new_config.get('concatenation') or
                    self.config.get('concatenation_time') != new_config.get('concatenation_time') or
                    self.config.get('deletion_time') != new_config.get('deletion_time')
                )

                if config_changed:
                    self.logger.info("Configuration changes detected, applying updates...")
                    self.config = new_config

                    # Re-setup components
                    self.setup_recorders()
                    self.setup_schedules()

                    self.logger.info("Configuration hot-reload completed successfully")
                else:
                    self.logger.debug("No significant configuration changes detected")

        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {str(e)}")

    def initial_directories(self):
        """Create directory for current date for all cameras"""
        current_date = datetime.now().strftime('%Y-%m-%d')
        self.logger.debug(f"Creating initial directories for date: {current_date}")

        with self._lock:
            for camera_name in self.recorders.keys():
                date_dir = f"/storage/{camera_name}/{current_date}"
                os.makedirs(date_dir, exist_ok=True)
                self.logger.debug(f"Directory created/verified: {date_dir}")

    def start(self):
        self.logger.info("Starting OneNVR recorders")

        # Ensure initial directories exist
        self.initial_directories()

        # Start all recorders
        with self._lock:
            for recorder in self.recorders.values():
                try:
                    recorder.start()
                except Exception as e:
                    self.logger.error(f"Failed to start recorder: {str(e)}")

        # Main loop
        self.logger.debug("Entering main loop")
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}")
                time.sleep(5)

    def stop(self):
        """Gracefully stop the NVR system."""
        self.logger.info("Stopping OneNVR system")

        # Stop config watcher
        if self.config_watcher:
            self.config_watcher.stop()

        # Stop all recorders
        with self._lock:
            for recorder in self.recorders.values():
                try:
                    recorder.stop()
                except Exception as e:
                    self.logger.error(f"Error stopping recorder: {str(e)}")

        self.logger.debug("All recorders stopped")

    def health_check(self):
        """Check health of all camera recorders."""
        self.logger.debug("Starting health check for all cameras")
        with self._lock:
            for name, recorder in self.recorders.items():
                try:
                    self.logger.debug(f"Checking health for camera: {name}")
                    if not recorder.is_healthy():
                        if recorder.manually_stopped:
                            self.logger.debug(f"Skipping restart for manually stopped camera: {name}")
                        else:
                            self.logger.warning(f"Restarting unhealthy camera: {name}")
                            recorder.restart()
                    else:
                        self.logger.debug(f"Camera {name} is healthy")
                except Exception as e:
                    self.logger.error(f"Error in health check for {name}: {str(e)}")

    def disk_space_check(self):
        """Monitor disk space and alert if running low."""
        try:
            stat = shutil.disk_usage("/storage")
            total_gb = stat.total / (1024**3)
            free_gb = stat.free / (1024**3)
            used_percent = (stat.used / stat.total) * 100

            # Log status at different thresholds
            if free_gb < 1:  # Less than 1GB
                self.logger.critical(f"CRITICAL: Disk space critically low: {free_gb:.2f}GB remaining ({used_percent:.1f}% used)")
            elif free_gb < 5:  # Less than 5GB
                self.logger.error(f"WARNING: Disk space low: {free_gb:.2f}GB remaining ({used_percent:.1f}% used)")
            elif used_percent > 90:
                self.logger.warning(f"Disk usage high: {used_percent:.1f}% used, {free_gb:.2f}GB free")
            else:
                self.logger.debug(f"Disk space OK: {free_gb:.2f}GB free ({used_percent:.1f}% used)")

            # Trigger immediate cleanup if critically low
            if free_gb < 2:
                self.logger.warning("Triggering emergency cleanup due to low disk space")
                self.video_manager.cleanup_old_recordings(emergency=True)

        except Exception as e:
            self.logger.error(f"Failed to check disk space: {str(e)}")

    def concatenate_all_cameras(self):
        """Concatenate videos for all cameras."""
        self.logger.info("Starting daily video concatenation")
        with self._lock:
            for camera_name in self.recorders.keys():
                try:
                    self.logger.debug(f"Starting concatenation for camera: {camera_name}")
                    self.video_manager.concatenate_daily_videos(camera_name)
                except Exception as e:
                    self.logger.error(f"Error concatenating videos for {camera_name}: {str(e)}")
            self.logger.debug("Daily concatenation complete for all cameras")

    def start_web_server(self):
        """Start the Flask web interface."""
        self.logger.debug("Creating web server")
        self.web_app = create_web_server(nvr_system=self)
        self.logger.debug("Starting web server thread")
        server_thread = threading.Thread(
            target=self.web_app.run,
            kwargs={'host': '0.0.0.0', 'port': 5000, 'threaded': True},
            daemon=True
        )
        server_thread.start()
        self.logger.info("OneNVR web server started on port 5000")

if __name__ == "__main__":
    try:
        nvr = NVRSystem()
        nvr.start()
    except Exception as e:
        logger.error(f"Failed to start OneNVR system: {str(e)}")
        raise
