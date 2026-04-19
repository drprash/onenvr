# src/app/onvif_discovery.py
import subprocess
import logging
import urllib.parse
from onvif import ONVIFCamera
from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery
from ip_resolver import IPResolver, UnresolvableError

logger = logging.getLogger(__name__)


def build_rtsp_url(resolved_ip: str, raw_url: str, username: str, password: str) -> str:
    parsed = urllib.parse.urlparse(raw_url)
    if username:
        enc_user = urllib.parse.quote(username, safe='')
        enc_pass = urllib.parse.quote(password, safe='')
        netloc = f"{enc_user}:{enc_pass}@{resolved_ip}"
        if parsed.port:
            netloc += f":{parsed.port}"
    else:
        netloc = resolved_ip
        if parsed.port:
            netloc += f":{parsed.port}"
    return parsed._replace(netloc=netloc).geturl()


def probe_rtsp(rtsp_url: str, timeout: int) -> bool:
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-loglevel', 'error',
             '-rtsp_transport', 'tcp', '-t', str(timeout), '-i', rtsp_url, '-f', 'null', '-'],
            capture_output=True,
            timeout=timeout + 5
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        logger.debug(f"RTSP probe error: {e}")
        return False


class ONVIFDiscovery:
    def __init__(self, onvif_timeout: int = 5, rtsp_probe_timeout: int = 3):
        self.onvif_timeout = onvif_timeout
        self.rtsp_probe_timeout = rtsp_probe_timeout

    def scan(self) -> list:
        candidates = []
        wsd = WSDiscovery()
        wsd.start()
        try:
            services = wsd.searchServices(timeout=self.onvif_timeout)
        finally:
            wsd.stop()

        for svc in services:
            xaddrs = svc.getXAddrs()
            if not xaddrs:
                continue
            xaddr = xaddrs[0]
            try:
                candidate = self._probe_device(xaddr)
                candidates.append(candidate)
            except Exception as e:
                logger.warning(f"ONVIF error for {xaddr}: {e}")
                candidates.append({
                    'ip': self._extract_ip(xaddr),
                    'mac': '',
                    'name': '',
                    'model': '',
                    'onvif_port': 80,
                    'rtsp_url': '',
                    'requires_auth': False,
                    'status': 'onvif_error',
                    'error': str(e),
                })
        return candidates

    def _extract_ip(self, xaddr: str) -> str:
        try:
            return urllib.parse.urlparse(xaddr).hostname or ''
        except Exception:
            return ''

    def _probe_device(self, xaddr: str) -> dict:
        parsed = urllib.parse.urlparse(xaddr)
        ip = parsed.hostname
        port = parsed.port or 80

        cam = ONVIFCamera(ip, port, '', '', '/etc/onvif/wsdl/')
        cam.update_xaddrs()

        info = cam.devicemgmt.GetDeviceInformation()
        model = f"{info.Manufacturer} {info.Model}".strip()

        mac = ''
        try:
            ifaces = cam.devicemgmt.GetNetworkInterfaces()
            for iface in ifaces:
                if hasattr(iface, 'Info') and hasattr(iface.Info, 'HwAddress'):
                    mac = iface.Info.HwAddress
                    break
        except Exception:
            pass

        resolver = IPResolver()
        try:
            resolved_ip = resolver.resolve(ip, mac=mac, onvif_port=port)
        except UnresolvableError:
            resolved_ip = ip

        profiles = cam.media.GetProfiles()
        rtsp_url = ''
        if profiles:
            stream_setup = cam.media.create_type('GetStreamUri')
            stream_setup.ProfileToken = profiles[0].token
            stream_setup.StreamSetup = {
                'Stream': 'RTP-Unicast',
                'Transport': {'Protocol': 'RTSP'}
            }
            uri = cam.media.GetStreamUri(stream_setup)
            rtsp_url = build_rtsp_url(resolved_ip, uri.Uri, '', '')

        reachable = probe_rtsp(rtsp_url, self.rtsp_probe_timeout) if rtsp_url else False

        return {
            'ip': resolved_ip,
            'mac': mac,
            'name': info.SerialNumber or resolved_ip,
            'model': model,
            'onvif_port': port,
            'rtsp_url': rtsp_url,
            'requires_auth': not reachable,
            'status': 'ok' if reachable else 'auth_required',
            'error': '',
        }

    def validate_credential(self, ip: str, mac: str, onvif_port: int,
                            username: str, password: str, rtsp_url: str) -> dict:
        authed_url = build_rtsp_url(ip, rtsp_url, username, password)
        valid = probe_rtsp(authed_url, self.rtsp_probe_timeout)
        return {
            'rtsp_url': authed_url,
            'valid': valid,
            'error': '' if valid else 'RTSP connection failed with supplied credentials',
        }
