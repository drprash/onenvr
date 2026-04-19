# src/app/ip_resolver.py
import socket
import logging
import time
from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange

logger = logging.getLogger(__name__)


class UnresolvableError(Exception):
    pass


class IPResolver:
    def resolve(self, reported_ip: str, mac: str, onvif_port: int) -> str:
        if self._strategy_socket(reported_ip, onvif_port):
            return reported_ip

        if not mac:
            raise UnresolvableError(f"Socket verify failed for {reported_ip} and no MAC available")

        ip = self._strategy_arp(mac)
        if ip:
            logger.info(f"ARP resolved {mac} -> {ip} (was {reported_ip})")
            return ip

        ip = self._strategy_mdns(mac)
        if ip:
            logger.info(f"mDNS resolved {mac} -> {ip} (was {reported_ip})")
            return ip

        raise UnresolvableError(f"All resolution strategies failed for {reported_ip} / MAC {mac}")

    def _strategy_socket(self, ip: str, port: int, timeout: float = 1.0) -> bool:
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except OSError:
            return False

    def _strategy_arp(self, mac: str):
        mac_lower = mac.lower()
        try:
            with open('/proc/net/arp') as f:
                content = f.read()
            for line in content.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[3].lower() == mac_lower:
                    return parts[0]
        except Exception as e:
            logger.debug(f"ARP lookup failed: {e}")
        return None

    def _strategy_mdns(self, mac: str):
        found_ips = []
        mac_lower = mac.lower()

        def on_service_state_change(zeroconf, service_type, name, state_change):
            if state_change is ServiceStateChange.Added:
                info = zeroconf.get_service_info(service_type, name)
                if info:
                    found_ips.append((info, mac_lower))

        zc = Zeroconf()
        try:
            for stype in ('_onvif._tcp.local.', '_rtsp._tcp.local.'):
                ServiceBrowser(zc, stype, handlers=[on_service_state_change])
            time.sleep(3)
            return self._mdns_match(found_ips, mac_lower)
        finally:
            zc.close()

    def _mdns_match(self, found_ips, mac_lower: str):
        for info, expected_mac in found_ips:
            props = info.properties or {}
            for key in (b'mac', b'MAC'):
                val = props.get(key, b'')
                if isinstance(val, bytes):
                    val = val.decode('utf-8', errors='ignore')
                if val.lower() == expected_mac:
                    addrs = info.parsed_addresses()
                    if addrs:
                        return addrs[0]
        return None
