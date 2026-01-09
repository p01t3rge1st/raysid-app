# RAYSID PROTOCOL REFERENCE FOR LLM

## CONTEXT
Raysid gamma spectrometer BLE device. Nordic UART Service. Python + PyQt5 + bleak + asyncio.

## BLE UUIDS
```
TX (write): 49535343-8841-43f4-a8d4-ecbe34729bb3
RX (notify): 49535343-1e4d-4bd9-ba61-23c647249616
```

## PACKET TYPES
| Type | Hex | Description |
|------|-----|-------------|
| CPS | 0x17 | Counts per second + dose rate |
| Battery | 0x02 | Battery level + temperature |
| Spectrum Full | 0x30 | div=1, ~1800 channels, tiles |
| Spectrum Med | 0x31 | div=3, ~600 channels, tiles |
| Spectrum Low | 0x32 | div=9, ~200 channels, full |

## PACKET STRUCTURE
```
[length] [type] [data...] [checksum 3B]
length=0 means 256 bytes
```

## CRC ALGORITHMS

### CRC1 (32-bit sum, little-endian chunks)
```python
def crc1(data: bytes) -> int:
    crc, i = 0, 0
    while i < len(data):
        rem = len(data) - i
        if rem >= 4: crc += (data[i+3]<<24)|(data[i+2]<<16)|(data[i+1]<<8)|data[i]; i += 4
        elif rem == 3: crc += (data[i+2]<<16)|(data[i+1]<<8)|data[i]; i += 3
        elif rem == 2: crc += (data[i+1]<<8)|data[i]; i += 2
        else: crc += data[i]; i += 1
    return crc & 0xFFFFFFFF
```

### CRC2 (XOR all bytes)
```python
def crc2(data: bytes) -> int:
    return reduce(lambda a,b: a^b, data, 0) & 0xFF
```

### Checksum3 (XOR 3-byte groups)
```python
def checksum3(data: bytes) -> int:
    out = 0
    for i in range(0, len(data), 3):
        v = (data[i] << 16) if i < len(data) else 0
        v |= (data[i+1] << 8) if i+1 < len(data) else 0
        v |= data[i+2] if i+2 < len(data) else 0
        out ^= v
    return out & 0xFFFFFF
```

## COMMAND WRAPPING
```python
def wrap(payload):
    crc1_val = crc1(payload)
    inner = b'\xEE' + crc1_val.to_bytes(4,'big') + payload
    crc2_val = crc2(inner)
    pkt = bytes([0xFF, crc2_val]) + inner
    return pkt + bytes([len(pkt)+1])
```

## VALUE UNPACKING (logarithmic compression)
```python
def unpack(v: int) -> int:
    mult10, res = v // 6000, v % 6000
    for _ in range(mult10): res *= 10
    return res
```
Examples: 1234→1234, 6500→5000, 12100→10000

## CPS PACKET (0x17)
```
Structure: [len][0x17][type0][val_lo][val_hi][type1][val_lo][val_hi]...[chksum3][len]
type=0: CPS, type=1: dose_rate
```
```python
cps = unpack(raw_value) / 600.0
dose_rate = unpack(raw_value) / 60000.0  # µSv/h
```

## BATTERY PACKET (0x02)
```
[len][0x02][temp_lo][temp_hi][level%][charging]
temperature = (temp_lo | temp_hi<<8) / 10.0 - 100.0
level = byte[4]  # 0-100%
```

## SPECTRUM PACKET (0x30/0x31/0x32) - CRITICAL ALGORITHM

### Header
```
Byte 0: length (0=256)
Byte 1: type (0x30/0x31/0x32)
Byte 2-3: start_ch (LITTLE-ENDIAN) - FULL-RES channel index!
Byte 4-6: cur_val (BIG-ENDIAN, 3 bytes) - initial value
Byte 7+: differential encoded data
Last 3 bytes: checksum (excluded from parsing)
```

### Resolution
```
0x30: div=1 (full-res tiles)
0x31: div=3 (medium tiles)  
0x32: div=9 (low-res full spectrum)
```

### Channel Mapping
```python
# Parser: convert full-res start_ch to compressed index
x = start_ch // div

# Widget: expand compressed back to full-res
for i in range(div):
    spectrum[ch * div + i] = value
```

### Point Types (differential encoding)
```python
if byte == 0:
    point_type, points_amount = 4, 1
else:
    point_type = byte // 64      # bits 7-6
    points_amount = byte % 64    # bits 5-0
```

| Type | Bits | Values/Bytes | Signed Range |
|------|------|--------------|--------------|
| 0 | 4 | 2 per byte (nibbles) | -8 to +7 |
| 1 | 8 | 1 per byte | -128 to +127 |
| 2 | 12 | 2 per 3 bytes | -2048 to +2047 |
| 3 | 16 | 1 per 2 bytes (LE) | -32768 to +32767 |
| 4 | 24 | 1 per 3 bytes (LE) | -8388608 to +8388607 |

### Signed Conversion
```python
# 4-bit:  if v > 7: v -= 16
# 8-bit:  if v > 127: v -= 256
# 12-bit: if v > 2047: v -= 4096
# 16-bit: if v > 32767: v -= 65536
# 24-bit: if v > 8388607: v -= 16777216
```

### Type 0 Decoding (4-bit nibbles)
```python
while amount < points_amount:
    b = frame[pos]
    # High nibble
    diff = b // 16
    if diff > 7: diff -= 16
    cur_val += diff
    bins[x] = cur_val / div
    x += 1; amount += 1
    # Low nibble
    if amount < points_amount:
        diff = b % 16
        if diff > 7: diff -= 16
        cur_val += diff
        bins[x] = cur_val / div
        x += 1; amount += 1
    pos += 1
```

### Type 1 Decoding (8-bit signed)
```python
while amount < points_amount:
    diff = frame[pos]
    if diff > 127: diff -= 256
    cur_val += diff
    bins[x] = cur_val / div
    x += 1; amount += 1; pos += 1
```

### Type 2 Decoding (12-bit pairs)
```python
b0, b1 = frame[pos], frame[pos+1]
diff = ((b0 << 4) | (b1 >> 4)) & 0xFFF
if diff > 2047: diff -= 4096
cur_val += diff
bins[x] = cur_val / div; x += 1; pos += 2

b2 = frame[pos]
diff = ((b1 & 0xF) << 8) | b2
if diff > 2047: diff -= 4096
cur_val += diff
bins[x] = cur_val / div; x += 1; pos += 1
```

### Type 3 Decoding (16-bit LE)
```python
diff = frame[pos] | (frame[pos+1] << 8)
if diff > 32767: diff -= 65536
cur_val += diff
bins[x] = cur_val / div; x += 1; pos += 2
```

### Type 4 Decoding (24-bit LE)
```python
diff = frame[pos] | (frame[pos+1] << 8) | (frame[pos+2] << 16)
if diff > 8388607: diff -= 16777216
cur_val += diff
bins[x] = cur_val / div; x += 1; pos += 3
```

## BLE FRAGMENTATION
Large packets (256B) arrive in ~13 notifications (~20B each).
Buffer with 500ms timeout. Reset if new packet header detected mid-assembly.

## ENERGY CALIBRATION
```python
KEV_PER_CHANNEL = 0.446  # for 1800 channels
# Cs-137 peak (662 keV) at channel ~1485
energy_kev = channel * 0.446
```

## PING PACKET
```python
payload = bytes([0x12, tab, unix>>24, unix>>16, unix>>8, unix])
# tab=0 for CPS view, tab=1 for Spectrum view
```

## HELLO PACKET
```python
HELLO = bytes([0xFF,0xEE,0xEE,0x17,0x64,0x8F,0x32,0x12,0x00,0x64,0x17,0x20,0x8F,0x0E])
# Send twice with 200ms delay after connect
```

## COMPLETE SPECTRUM PARSER
```python
def parse_spectrum(frame):
    length = frame[0] or 256
    limit = length - 3
    ptype = frame[1]
    div = {0x30:1, 0x31:3, 0x32:9}[ptype]
    
    start_ch = frame[2] | (frame[3] << 8)  # LE!
    cur_val = (frame[6] << 16) | (frame[5] << 8) | frame[4]  # BE!
    
    bins = {}
    x = start_ch // div  # Convert to compressed index
    bins[x] = cur_val / div
    x += 1
    
    pos = 7
    while pos < limit and x < 1800//div + 10:
        b = frame[pos]
        if b == 0: pt, amt = 4, 1
        else: pt, amt = b//64, b%64
        pos += 1
        
        # Decode based on pt (0-4)
        # Apply signed conversion
        # cur_val += diff
        # bins[x] = cur_val / div
        # x += 1
    
    return {"type":"spectrum", "bins":bins, "div":div}
```

## KEY INVARIANTS
1. start_ch is ALWAYS full-res (0-1799)
2. Parser stores in compressed indices (÷div)
3. Widget expands to full-res (×div)
4. Values normalized by div in parser
5. Little-endian for most values except cur_val (big-endian)

## FILE STRUCTURE
```
app/
├── main.py              # Entry point, qasync integration
├── ble_worker.py        # BLE communication + packet parsing
├── widgets/
│   ├── main_window.py   # Main UI, connection management
│   ├── spectrum_widget.py # Matplotlib spectrum plot
│   ├── cps_widget.py    # CPS/dose display
│   └── settings_dialog.py # Peak/smooth settings
└── DOKUMENTACJA_*.md    # This documentation
```
