"""BLE communication worker for Raysid device."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Optional, Callable, Dict

from PyQt5.QtCore import QObject, pyqtSignal

from bleak import BleakClient

# File logger for debugging (writes to user's home directory)
_log_path = os.path.join(os.path.expanduser("~"), ".raysid_debug.log")
try:
    _log_file = open(_log_path, "a")
except (IOError, PermissionError):
    _log_file = None

def log_to_file(msg: str):
    if _log_file is None:
        return
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    _log_file.write(f"{ts} {msg}\n")
    _log_file.flush()


class BleWorker(QObject):
    """Handles BLE communication with Raysid device."""

    # Signals
    packet_received = pyqtSignal(dict)
    connection_lost = pyqtSignal()

    # Nordic UART UUIDs
    TX_UUID = "49535343-8841-43f4-a8d4-ecbe34729bb3"
    RX_UUID = "49535343-1e4d-4bd9-ba61-23c647249616"

    # Packet types
    SPECTRUM_TYPES = {0x30, 0x31, 0x32}

    def __init__(self, address: str, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.address = address
        self.device_address = address  # For reconnect
        self.loop = loop
        self.client: Optional[BleakClient] = None
        self.connected = False
        self.logger = logging.getLogger("raysid.ble")

        # Spectrum state
        self.spectrum_bins = {}
        self.spectrum_div = 1
        self.spectrum_cur_val = 0

        # Stream buffer for reassembly (unused now, kept for compatibility)
        self._buffer = bytearray()
        
        # Separate buffer for spectrum packets (256 bytes, fragmented over ~13 notifications)
        self._spectrum_buffer = bytearray()
        self._spectrum_expected_len = 0
        self._spectrum_buffer_start_time = 0.0  # For timeout detection
        
        log_to_file("=== BleWorker initialized ===")

    async def connect(self):
        """Connect to the device and start notifications."""
        log_to_file(f"Connecting to {self.address}")
        self.client = BleakClient(self.address, disconnected_callback=self._on_disconnect)
        await self.client.connect(timeout=15.0)
        if not self.client.is_connected:
            raise RuntimeError("Failed to connect")

        await self.client.start_notify(self.RX_UUID, self._notification_handler)
        self.connected = True

        # Send HELLO packets
        hello = bytes([0xFF, 0xEE, 0xEE, 0x17, 0x64, 0x8F, 0x32, 0x12, 0x00, 0x64, 0x17, 0x20, 0x8F, 0x0E])
        await self.client.write_gatt_char(self.TX_UUID, hello)
        await asyncio.sleep(0.2)
        await self.client.write_gatt_char(self.TX_UUID, hello)

        self.logger.info("Connected to %s", self.address)

    async def disconnect(self):
        """Disconnect from device."""
        if self.client and self.client.is_connected:
            await self.client.stop_notify(self.RX_UUID)
            await self.client.disconnect()
        self.connected = False
        self.logger.info("Disconnected")

    def _on_disconnect(self, client):
        self.connected = False
        self.connection_lost.emit()

    async def send_ping(self, tab: int):
        """Send PING packet with tab value (0=CPS, 1=Spectrum)."""
        if not self.connected or not self.client:
            return
        try:
            unix = int(time.time())
            payload = bytes([
                0x12,
                tab & 0xFF,
                (unix >> 24) & 0xFF,
                (unix >> 16) & 0xFF,
                (unix >> 8) & 0xFF,
                unix & 0xFF,
            ])
            packet = self._wrap_command(payload)
            await self.client.write_gatt_char(self.TX_UUID, packet)
        except Exception as e:
            self.logger.warning(f"send_ping failed: {e}")
            # Connection likely lost, trigger disconnect
            self.connected = False
            self.connection_lost.emit()

    async def request_spectrum(self, start: int = 0, end: int = 1799):
        """Request spectrum data."""
        if not self.connected or not self.client:
            return
        try:
            payload = bytes([
                0x3E,
                (start >> 8) & 0xFF,
                start & 0xFF,
                ((end + 1) >> 8) & 0xFF,
                (end + 1) & 0xFF,
            ])
            packet = self._wrap_command(payload)
            await self.client.write_gatt_char(self.TX_UUID, packet)
        except Exception as e:
            self.logger.warning(f"request_spectrum failed: {e}")

    def _wrap_command(self, payload: bytes) -> bytes:
        """Wrap payload in Raysid protocol frame."""
        crc1 = self._crc1(payload)
        inner = bytes([0xEE]) + crc1.to_bytes(4, 'big') + payload
        crc2 = self._crc2(inner)
        packet = bytes([0xFF, crc2]) + inner
        size = len(packet) + 1
        packet += bytes([size])
        return packet

    @staticmethod
    def _crc1(data: bytes) -> int:
        crc = 0
        i = 0
        ln = len(data)
        while i < ln:
            rem = ln - i
            if rem >= 4:
                crc += (data[i+3] << 24) | (data[i+2] << 16) | (data[i+1] << 8) | data[i]
                i += 4
            elif rem == 3:
                crc += (data[i+2] << 16) | (data[i+1] << 8) | data[i]
                i += 3
            elif rem == 2:
                crc += (data[i+1] << 8) | data[i]
                i += 2
            else:
                crc += data[i]
                i += 1
        return crc & 0xFFFFFFFF

    @staticmethod
    def _crc2(data: bytes) -> int:
        out = 0
        for b in data:
            out ^= b
        return out & 0xFF

    @staticmethod
    def _checksum3(data: bytes) -> int:
        """Checksum3: XOR of 3-byte big-endian words.
        
        Used to validate spectrum packets (type 0x30/0x31/0x32).
        Spectrum frame structure: [len][type][...data...][chk1][chk2][chk3]
        where checksum3 is calculated over all bytes EXCEPT the last 3 checksum bytes.
        """
        out = 0
        length = len(data)
        for i in range(0, length, 3):
            value = 0
            if i < length:
                value |= (data[i] & 0xFF) << 16
            if i + 1 < length:
                value |= (data[i + 1] & 0xFF) << 8
            if i + 2 < length:
                value |= data[i + 2] & 0xFF
            out ^= value
        return out & 0xFFFFFF

    def _validate_spectrum_checksum(self, frame: bytes) -> bool:
        """Validate spectrum packet checksum (last 3 bytes, little-endian).
        
        Returns True if checksum matches, False otherwise.
        Checksum is stored as little-endian 3-byte value at the end of frame.
        """
        if len(frame) < 6:
            return False
        
        # Last 3 bytes are checksum (little-endian)
        chk_bytes = frame[-3:]
        # Convert from little-endian to integer
        expected = (chk_bytes[2] << 16) | (chk_bytes[1] << 8) | chk_bytes[0]
        
        # Calculate checksum over all bytes except the last 3
        core = frame[:-3]
        calculated = self._checksum3(core)
        
        is_valid = (calculated == expected)
        ptype = frame[1] if len(frame) > 1 else 0
        length = frame[0] or 256
        
        if is_valid:
            msg = f"{self.GREEN}[SPECTRUM ✓ ACCEPT]{self.RESET} type=0x{ptype:02X} len={length} checksum={expected:06X}"
            print(msg)
            log_to_file(f"[SPECTRUM ✓ ACCEPT] type=0x{ptype:02X} len={length} checksum={expected:06X}")
        else:
            msg = f"{self.RED}[SPECTRUM ✗ REJECT]{self.RESET} type=0x{ptype:02X} len={length} expected={expected:06X} calculated={calculated:06X}"
            print(msg)
            log_to_file(f"[SPECTRUM ✗ REJECT] type=0x{ptype:02X} len={length} expected={expected:06X} calculated={calculated:06X}")
        
        return is_valid

    def _notification_handler(self, handle, data: bytearray):
        """Handle incoming BLE notifications.
        
        Small packets (CPS, Battery) arrive complete in one notification.
        Large spectrum packets (256 bytes, length_byte=0) are fragmented across ~13 notifications.
        Small spectrum packets (type 0x31, 0x32) arrive complete.
        """
        raw = bytes(data)
        # Verbose log disabled - uncomment for debugging:
        # log_to_file(f"[NOTIFY] len={len(raw)} raw={raw.hex()}")
        
        now = time.time()
        
        # Timeout check - if buffer is stale (>500ms), reset it
        if self._spectrum_expected_len > 0:
            elapsed = now - self._spectrum_buffer_start_time
            if elapsed > 0.5:
                log_to_file(f"[SPEC BUFFER] TIMEOUT after {elapsed:.3f}s - resetting")
                self._spectrum_buffer.clear()
                self._spectrum_expected_len = 0
        
        # Check if this looks like a new packet start (has valid length and type)
        is_new_packet = False
        if len(raw) >= 2:
            length_byte = raw[0]
            ptype = raw[1]
            # Valid packet types we recognize
            if ptype in self.SPECTRUM_TYPES or ptype in {0x02, 0x17}:
                declared_len = 256 if length_byte == 0 else length_byte
                if 4 <= declared_len <= 256:
                    is_new_packet = True
        
        # If we're assembling a 256-byte spectrum and this looks like a new packet,
        # cancel the current assembly (data corruption recovery)
        if self._spectrum_expected_len > 0 and is_new_packet and len(raw) > 10:
            log_to_file(f"[SPEC BUFFER] RESET - new packet detected while assembling")
            self._spectrum_buffer.clear()
            self._spectrum_expected_len = 0
        
        # Check if we're currently assembling a 256-byte spectrum packet
        if self._spectrum_expected_len > 0:
            # Continue assembling spectrum
            self._spectrum_buffer.extend(raw)
            log_to_file(f"[SPEC BUFFER] added {len(raw)}, total={len(self._spectrum_buffer)}/{self._spectrum_expected_len}")
            
            if len(self._spectrum_buffer) >= self._spectrum_expected_len:
                # Complete spectrum packet
                frame = bytes(self._spectrum_buffer[:self._spectrum_expected_len])
                log_to_file(f"[SPEC COMPLETE] len={len(frame)}")
                self._spectrum_buffer.clear()
                self._spectrum_expected_len = 0
                self._parse_frame(frame)
            return
        
        # New packet - check type
        if len(raw) >= 2:
            length_byte = raw[0]
            ptype = raw[1]
            declared_len = 256 if length_byte == 0 else length_byte
            
            # ALL spectrum packets need buffering (both small and large)
            # because they can arrive fragmented across multiple notifications
            if ptype in self.SPECTRUM_TYPES:
                # Start buffering spectrum (small or large)
                self._spectrum_buffer = bytearray(raw)
                self._spectrum_expected_len = declared_len
                self._spectrum_buffer_start_time = now
                log_to_file(f"[SPEC START] type=0x{ptype:02X} len={declared_len} buffering {len(raw)}/{declared_len}")
                return
        
        # Complete packet (CPS, Battery) - parse directly
        self._parse_frame(raw)

    def _process_buffer(self):
        """Extract and parse complete frames from buffer."""
        while len(self._buffer) >= 4:
            length_byte = self._buffer[0]
            declared = 256 if length_byte == 0 else length_byte

            if declared > 256 or declared < 4:
                # Invalid, drop byte
                del self._buffer[0]
                continue

            if len(self._buffer) < declared:
                # Wait for more data
                break

            frame = bytes(self._buffer[:declared])
            del self._buffer[:declared]
            self._parse_frame(frame)

    # ANSI colors for debug
    RED = "\033[91m"
    GREEN = "\033[92m"
    RESET = "\033[0m"

    def _parse_frame(self, frame: bytes):
        """Parse a complete frame and emit signal."""
        if len(frame) < 4:
            return

        ptype = frame[1]
        log_to_file(f"[FRAME] type=0x{ptype:02X} len={len(frame)} raw={frame[:20].hex()}")

        if ptype == 0x17:
            # CPS packet
            pkt = self._parse_cps(frame)
            if pkt:
                log_to_file(f"[CPS ✓] cps={pkt.get('cps'):.2f} dose={pkt.get('dose_rate'):.3f}")
                self.packet_received.emit(pkt)
            else:
                log_to_file("[CPS] parse returned None")

        elif ptype == 0x02:
            # Battery/status packet
            pkt = self._parse_battery(frame)
            if pkt:
                log_to_file(f"[BATT ✓] level={pkt.get('level')}% temp={pkt.get('temperature'):.1f}°C")
                self.packet_received.emit(pkt)

        elif ptype in self.SPECTRUM_TYPES:
            # Spectrum packet
            pkt = self._parse_spectrum(frame)
            if pkt:
                log_to_file(f"[SPEC ✓] type=0x{ptype:02X} bins={len(pkt.get('bins', {}))} last_ch={pkt.get('last_channel')}")
                self.packet_received.emit(pkt)
            else:
                log_to_file(f"[SPEC ✗] type=0x{ptype:02X} len={len(frame)} REJECTED")

    def _parse_cps(self, frame: bytes) -> Optional[Dict]:
        """Parse CPS packet (type 0x17) - from working cps_reader.py."""
        if len(frame) < 13 or frame[1] != 0x17:
            log_to_file(f"[CPS ✗] rejected: len={len(frame)} (need >=13)")
            return None
        
        # Checksum validation
        checksum_ok = self._validate_cps_checksum2b(frame)
        if not checksum_ok:
            log_to_file(f"[CPS ✗] checksum FAILED")
            return None
        
        log_to_file(f"[CPS] checksum OK, parsing data...")
        
        # Overload check
        overload = 0
        if frame[0] == 18 and len(frame) > 14:
            overload = frame[14] & 0xFF
        if overload > 1:
            log_to_file(f"[CPS] overload={overload} > 1, rejected")
            return None
        
        cps = None
        dose_rate = None
        
        sets = 2 if len(frame) <= 20 else 12
        log_to_file(f"[CPS] frame[0]={frame[0]} len={len(frame)} sets={sets}")
        
        for k in range(sets):
            idx_type = k * 3 + 2
            idx_val_lo = k * 3 + 3
            idx_val_hi = k * 3 + 4
            if idx_val_hi >= len(frame):
                break
            data_type = frame[idx_type] & 0xFF
            raw_value = ((frame[idx_val_hi] & 0xFF) << 8) | (frame[idx_val_lo] & 0xFF)
            unpacked = self._unpack_value(raw_value)
            value = unpacked / 600.0
            log_to_file(f"[CPS] k={k} data_type={data_type} raw={raw_value} unpacked={unpacked} value={value:.2f}")
            if data_type == 0:
                cps = value
            elif data_type == 1:
                dose_rate = value / 100.0  # Additional /100 for µSv/h display
        
        log_to_file(f"[CPS] FINAL: cps={cps} dose_rate={dose_rate}")
        
        return {
            "type": "cps",
            "cps": cps if cps is not None else 0,
            "dose_rate": dose_rate if dose_rate is not None else 0
        }

    @staticmethod
    def _checksum3(data: bytes) -> int:
        """3-byte XOR checksum."""
        out = 0
        length = len(data)
        for i in range(0, length, 3):
            value = 0
            if i < length:
                value |= (data[i] & 0xFF) << 16
            if i + 1 < length:
                value |= (data[i + 1] & 0xFF) << 8
            if i + 2 < length:
                value |= data[i + 2] & 0xFF
            out ^= value
        return out & 0xFFFFFF

    def _validate_cps_checksum2b(self, packet: bytes) -> bool:
        """Validate CPS packet checksum (2-byte comparison)."""
        if len(packet) < 7:
            return False
        calculated = self._checksum3(packet[1:-3])
        calc_bytes = calculated.to_bytes(3, 'big')
        calc_2b = calc_bytes[:2][::-1]  # [mid, high]
        exp_2b = packet[-4:-2]
        return calc_2b == exp_2b

    def _validate_checksum(self, packet: bytes) -> bool:
        """Validate packet checksum (3-byte XOR)."""
        if len(packet) < 7:
            return False
        # Calculate checksum over data (excluding last 3 bytes which are checksum + length)
        calculated = self._checksum3(packet[1:-3])
        calc_bytes = calculated.to_bytes(3, 'big')  # [high, mid, low]
        
        # Expected checksum is in packet[-4:-1] as [low, mid, high]
        exp_low = packet[-4] & 0xFF
        exp_mid = packet[-3] & 0xFF
        exp_high = packet[-2] & 0xFF
        
        # Compare
        return (calc_bytes[0] == exp_high and 
                calc_bytes[1] == exp_mid and 
                calc_bytes[2] == exp_low)

    @staticmethod
    def _unpack_value(v: int) -> int:
        """Unpack encoded value according to Raysid protocol."""
        mult10 = v // 6000
        res = v % 6000
        for _ in range(mult10):
            res *= 10
        return res

    def _parse_battery(self, frame: bytes) -> Optional[Dict]:
        """Parse battery/status packet (type 0x02)."""
        if len(frame) < 6 or frame[1] != 0x02:
            self.logger.debug(f"[BATTERY] rejected: len={len(frame)}")
            return None
        
        # Note: Battery packets don't use the same checksum format as CPS
        # They are validated by packet structure only
        
        # Temperature: bytes[2-3] little-endian, /10.0 - 100.0
        temp_raw = (frame[2] & 0xFF) | ((frame[3] & 0xFF) << 8)
        temperature = temp_raw / 10.0 - 100.0
        
        # Battery percent: byte[4]
        level = frame[4] & 0xFF
        
        # Is charging: byte[5]
        is_charging = bool(frame[5] & 0xFF) if len(frame) > 5 else False
        
        # Validate reasonable values - reject corrupted packets
        if level > 100 or temperature < -40 or temperature > 80:
            log_to_file(f"[BATT ✗] invalid values: level={level}% temp={temperature:.1f}°C - REJECTED")
            return None
        
        return {
            "type": "battery",
            "level": level,
            "temperature": temperature,
            "is_charging": is_charging
        }

    def _parse_spectrum(self, frame: bytes) -> Optional[Dict]:
        """Parse spectrum packet (type 0x30/0x31/0x32) using diff encoding from API1."""
        length = frame[0] or 256
        
        # Validate spectrum checksum (last 3 bytes)
        if not self._validate_spectrum_checksum(frame):
            log_to_file(f"[SPEC REJECT] checksum validation failed")
            return None
        
        # Note: Spectrum packets have checksum in last 3 bytes but format differs from CPS
        # The limit = length - 3 already excludes them from data parsing
        
        limit = length - 3  # exclude checksum bytes at end
        ptype = frame[1]

        div = 1
        if ptype == 0x31:
            div = 3
        elif ptype == 0x32:
            div = 9

        # Start channel: bytes[2],bytes[3] (little-endian, jak większość protokołu Raysid)
        start_ch = frame[2] | (frame[3] << 8)
        
        # Kafelki (tiles) mogą mieć start_ch w dowolnym miejscu spektrum.
        # 0x32 (div=9): ~200 kanałów kompresowanych → 0..1800 full-res
        # 0x31 (div=3): ~600 kanałów kompresowanych → 0..1800 full-res  
        # 0x30 (div=1): ~1800 kanałów → 0..1800 full-res
        # Nie ograniczamy start_ch - kafelki mogą zaczynać się gdziekolwiek.
        # Jedyna walidacja: start_ch musi być rozsądny (< 2000)
        if start_ch > 2000:
            log_to_file(f"[SPEC SKIP] Invalid start_ch={start_ch} for type=0x{ptype:02X}")
            return None
        
        # Initial value: bytes[6],bytes[5],bytes[4] (big-endian, 3 bytes)
        cur_val = (frame[6] << 16) | (frame[5] << 8) | frame[4]

        bins = {}
        # start_ch jest w jednostkach FULL-RES (0-1799), przeliczamy na kompresowane
        # Widget potem przemnoży przez div żeby uzyskać full-res
        x = start_ch // div
        # Limit w jednostkach kompresowanych
        max_channel = 1800 // div + 10  # Margines bezpieczeństwa

        # First value - single channel, normalized by div
        bins[x] = cur_val / float(div)
        x += 1

        pos = 7
        frame_len = len(frame)
        while pos < limit and pos < frame_len and x < max_channel:
            b = frame[pos]

            # Special case: bytes[pos]==0 means pointType=4, pointsAmount=1
            if b == 0:
                point_type = 4
                points_amount = 1
            else:
                point_type = (b & 0xFF) // 64
                points_amount = (b & 0xFF) % 64

            pos += 1

            if point_type == 0:
                # 2 values in 1 byte (4-bit nibbles)
                amount = 0
                while amount < points_amount and pos < limit and pos < frame_len:
                    bytev = frame[pos]
                    # High nibble
                    diff = (bytev & 0xFF) // 16
                    if diff > 7:
                        diff -= 16
                    cur_val += diff
                    bins[x] = cur_val / float(div)
                    x += 1
                    amount += 1

                    if amount < points_amount:
                        # Low nibble
                        diff = (bytev & 0xFF) % 16
                        if diff > 7:
                            diff -= 16
                        cur_val += diff
                        bins[x] = cur_val / float(div)
                        x += 1
                        amount += 1

                    pos += 1

            elif point_type == 1:
                # 1 value in 1 byte (signed 8-bit)
                amount = 0
                while amount < points_amount and pos < limit and pos < frame_len:
                    diff = frame[pos] & 0xFF
                    if diff > 127:
                        diff -= 256
                    cur_val += diff
                    bins[x] = cur_val / float(div)
                    x += 1
                    amount += 1
                    pos += 1

            elif point_type == 2:
                # 2 values in 3 bytes (12-bit each)
                amount = 0
                while amount < points_amount and pos + 1 < limit and pos + 1 < frame_len:
                    b0 = frame[pos]
                    b1 = frame[pos + 1]

                    # First 12-bit value
                    diff = ((b0 << 4) | ((b1 >> 4) & 0xF)) & 0xFFF
                    if diff > 2047:
                        diff -= 4096
                    cur_val += diff
                    bins[x] = cur_val / float(div)
                    x += 1
                    amount += 1
                    pos += 2

                    if amount < points_amount and pos < limit and pos < frame_len:
                        b2 = frame[pos]
                        # Second 12-bit value
                        diff = ((b1 & 0xF) << 8) | (b2 & 0xFF)
                        if diff > 2047:
                            diff -= 4096
                        cur_val += diff
                        bins[x] = cur_val / float(div)
                        x += 1
                        amount += 1
                        pos += 1

            elif point_type == 3:
                # 1 value in 2 bytes (signed 16-bit, little-endian)
                amount = 0
                while amount < points_amount and pos + 1 < limit and pos + 1 < frame_len:
                    diff = ((frame[pos + 1] & 0xFF) << 8) | (frame[pos] & 0xFF)
                    if diff > 32767:
                        diff -= 65536
                    cur_val += diff
                    bins[x] = cur_val / float(div)
                    x += 1
                    amount += 1
                    pos += 2

            elif point_type == 4:
                # 1 value in 3 bytes (signed 24-bit, little-endian)
                if pos + 2 < limit and pos + 2 < frame_len:
                    diff = (frame[pos + 2] << 16) | (frame[pos + 1] << 8) | frame[pos]
                    if diff > 8388607:
                        diff -= 16777216
                    cur_val += diff
                    bins[x] = cur_val / float(div)
                    x += 1
                    pos += 3
                else:
                    break

            else:
                break

        return {"type": "spectrum", "bins": bins, "last_channel": x, "div": div}
