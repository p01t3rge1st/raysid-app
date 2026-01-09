# Raysid Gamma Spectrometer - Dokumentacja Techniczna v1.0

## 📋 Spis treści

1. [Przegląd architektury](#1-przegląd-architektury)
2. [Komunikacja BLE](#2-komunikacja-ble)
3. [Protokół pakietów](#3-protokół-pakietów)
4. [Algorytmy dekodowania](#4-algorytmy-dekodowania)
5. [Widżety GUI](#5-widżety-gui)
6. [Kalibracja i przeliczniki](#6-kalibracja-i-przeliczniki)

---

## 1. Przegląd architektury

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py                                   │
│  - Punkt wejścia aplikacji                                       │
│  - Integracja PyQt5 + asyncio przez qasync                       │
│  - Obsługa sygnałów SIGINT/SIGTERM                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MainWindow                                   │
│  - Główne okno z zakładkami (Spectrum / CPS)                     │
│  - Zarządzanie połączeniem BLE                                   │
│  - Timer PING co 10 sekund                                       │
│  - QSettings dla persystencji urządzenia                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │ BleWorker  │  │ Spectrum   │  │ CPS        │
    │            │  │ Widget     │  │ Widget     │
    │ - bleak    │  │ - wykres   │  │ - liczniki │
    │ - parser   │  │ - piki     │  │ - historia │
    └────────────┘  └────────────┘  └────────────┘
```

### Kluczowe zależności:
- **PyQt5** - GUI framework
- **qasync** - integracja Qt event loop z asyncio
- **bleak** - biblioteka BLE (BlueZ D-Bus na Linux)
- **numpy** - operacje na tablicach spektrum
- **scipy** - wykrywanie pików, wygładzanie (opcjonalne)
- **matplotlib** - wykresy

### Zależności systemowe (Qt/X11)
- Linux (apt): `sudo apt-get install -y libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-image0 libxcb-render-util0 libxkbcommon-x11-0 libgl1`
- Fedora/RHEL (dnf): `sudo dnf install -y libxcb xcb-util xcb-util-image xcb-util-renderutil xcb-util-keysyms libxkbcommon-x11 mesa-libGL`
- Arch (pacman): `sudo pacman -Sy --noconfirm libxcb xcb-util xcb-util-image xcb-util-renderutil xcb-util-keysyms libxkbcommon-x11 mesa`
- Headless/CI: uruchamiaj przez `xvfb-run -s "-screen 0 1280x720x24" .venv/bin/python main.py`

---

## 2. Komunikacja BLE

### 2.1 Nordic UART Service (NUS)

Raysid używa Nordic UART Service do komunikacji:

```python
TX_UUID = "49535343-8841-43f4-a8d4-ecbe34729bb3"  # Wysyłanie DO urządzenia
RX_UUID = "49535343-1e4d-4bd9-ba61-23c647249616"  # Odbieranie OD urządzenia
```

### 2.2 Sekwencja połączenia

```
1. BleakScanner.discover() - skanowanie urządzeń "Raysid*"
2. BleakClient.connect(timeout=15.0) - nawiązanie połączenia
3. start_notify(RX_UUID, handler) - subskrypcja notyfikacji
4. write_gatt_char(TX_UUID, HELLO) - wysłanie pakietu HELLO (2x)
5. Timer PING co 10s - utrzymanie połączenia
```

### 2.3 Pakiet HELLO

```python
HELLO = bytes([0xFF, 0xEE, 0xEE, 0x17, 0x64, 0x8F, 0x32, 0x12, 
               0x00, 0x64, 0x17, 0x20, 0x8F, 0x0E])
```

Wysyłany dwukrotnie po połączeniu z opóźnieniem 200ms.

### 2.4 Pakiet PING

Utrzymuje połączenie i informuje urządzenie o aktywnej zakładce:

```python
async def send_ping(self, tab: int):
    unix = int(time.time())
    payload = bytes([
        0x12,                    # Typ: PING
        tab & 0xFF,              # 0=CPS, 1=Spectrum
        (unix >> 24) & 0xFF,     # Timestamp (big-endian)
        (unix >> 16) & 0xFF,
        (unix >> 8) & 0xFF,
        unix & 0xFF,
    ])
    packet = self._wrap_command(payload)
```

### 2.5 Opakowanie komend (_wrap_command)

Każda komenda musi być opakowana w protokół Raysid:

```python
def _wrap_command(self, payload: bytes) -> bytes:
    crc1 = self._crc1(payload)           # CRC danych
    inner = bytes([0xEE]) + crc1.to_bytes(4, 'big') + payload
    crc2 = self._crc2(inner)             # XOR całości
    packet = bytes([0xFF, crc2]) + inner
    size = len(packet) + 1
    packet += bytes([size])              # Długość na końcu
    return packet
```

**Struktura opakowanego pakietu:**
```
[0xFF] [CRC2] [0xEE] [CRC1: 4 bajty] [PAYLOAD...] [ROZMIAR]
```

### 2.6 Algorytmy CRC

**CRC1 - suma 32-bitowa (little-endian chunks):**
```python
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
```

**CRC2 - XOR wszystkich bajtów:**
```python
@staticmethod
def _crc2(data: bytes) -> int:
    out = 0
    for b in data:
        out ^= b
    return out & 0xFF
```

---

## 3. Protokół pakietów

### 3.1 Typy pakietów

| Typ | Hex | Opis | Rozmiar |
|-----|-----|------|---------|
| CPS | 0x17 | Zliczenia/dawka | 13-38 bajtów |
| Battery | 0x02 | Bateria/temp | 6+ bajtów |
| Spectrum Full | 0x30 | Pełna rozdzielczość (div=1) | 256 bajtów |
| Spectrum Med | 0x31 | Średnia rozdzielczość (div=3) | zmienny |
| Spectrum Low | 0x32 | Niska rozdzielczość (div=9) | zmienny |

### 3.2 Struktura nagłówka pakietu

```
Bajt 0: Długość (0 = 256 bajtów)
Bajt 1: Typ pakietu
Bajt 2+: Dane specyficzne dla typu
...
Ostatnie 3 bajty: Checksum
```

### 3.3 Fragmentacja BLE

Duże pakiety (256 bajtów) są dzielone na ~13 notyfikacji BLE (MTU ~20 bajtów):

```python
# Buforowanie fragmentów:
if ptype in SPECTRUM_TYPES and declared_len == 256:
    self._spectrum_buffer = bytearray(raw)
    self._spectrum_expected_len = 256
    self._spectrum_buffer_start_time = time.time()
    return

# Kontynuacja składania:
if self._spectrum_expected_len > 0:
    self._spectrum_buffer.extend(raw)
    if len(self._spectrum_buffer) >= self._spectrum_expected_len:
        frame = bytes(self._spectrum_buffer[:256])
        self._parse_frame(frame)
```

**Timeout buforowania:** 500ms - jeśli pakiet nie zostanie skompletowany, bufor jest czyszczony.

---

## 4. Algorytmy dekodowania

### 4.1 Pakiet CPS (0x17)

**Struktura:**
```
[długość] [0x17] [typ_danych_0] [wartość_lo] [wartość_hi] 
                 [typ_danych_1] [wartość_lo] [wartość_hi] ...
                 [checksum: 3 bajty] [długość]
```

**Typy danych:**
- `0` = CPS (zliczenia na sekundę)
- `1` = Dawka promieniowania

**Algorytm rozpakowania wartości (_unpack_value):**

Raysid używa kompresji logarytmicznej dla dużych wartości:

```python
@staticmethod
def _unpack_value(v: int) -> int:
    """
    Wartości > 6000 są kodowane logarytmicznie.
    mult10 = v // 6000 określa ile razy pomnożyć przez 10.
    """
    mult10 = v // 6000
    res = v % 6000
    for _ in range(mult10):
        res *= 10
    return res
```

**Przykłady:**
- `v = 1234` → `mult10=0, res=1234` → wynik: 1234
- `v = 6500` → `mult10=1, res=500` → wynik: 5000
- `v = 12100` → `mult10=2, res=100` → wynik: 10000

**Przeliczenie na jednostki:**
```python
value = unpacked / 600.0        # CPS
dose_rate = value / 100.0       # µSv/h (dodatkowe /100)
```

**Walidacja checksum (2-bajtowa):**
```python
def _validate_cps_checksum2b(self, packet: bytes) -> bool:
    calculated = self._checksum3(packet[1:-3])
    calc_bytes = calculated.to_bytes(3, 'big')
    calc_2b = calc_bytes[:2][::-1]  # [mid, high] odwrócone
    exp_2b = packet[-4:-2]
    return calc_2b == exp_2b
```

**Checksum3 - XOR po 3 bajty:**
```python
@staticmethod
def _checksum3(data: bytes) -> int:
    out = 0
    for i in range(0, len(data), 3):
        value = 0
        if i < len(data):
            value |= (data[i] & 0xFF) << 16
        if i + 1 < len(data):
            value |= (data[i + 1] & 0xFF) << 8
        if i + 2 < len(data):
            value |= data[i + 2] & 0xFF
        out ^= value
    return out & 0xFFFFFF
```

### 4.2 Pakiet Battery (0x02)

**Struktura:**
```
[długość] [0x02] [temp_lo] [temp_hi] [poziom%] [ładowanie] ...
```

**Dekodowanie:**
```python
# Temperatura: little-endian, /10.0 - 100.0
temp_raw = frame[2] | (frame[3] << 8)
temperature = temp_raw / 10.0 - 100.0

# Poziom baterii: 0-100%
level = frame[4] & 0xFF

# Czy ładuje: boolean
is_charging = bool(frame[5] & 0xFF)
```

**Walidacja:**
```python
if level > 100 or temperature < -40 or temperature > 80:
    return None  # Odrzuć uszkodzony pakiet
```

### 4.3 Pakiety Spectrum (0x30/0x31/0x32) - NAJWAŻNIEJSZY ALGORYTM

#### 4.3.1 Koncepcja kompresji różnicowej

Spektrum gamma ma 1800 kanałów. Zamiast wysyłać wartość każdego kanału, Raysid wysyła:
1. **Wartość początkową** (cur_val)
2. **Różnice (delty)** do kolejnych wartości

To drastycznie zmniejsza rozmiar danych, ponieważ sąsiednie kanały mają podobne wartości.

#### 4.3.2 Trzy poziomy rozdzielczości

| Typ | div | Kanały | Opis |
|-----|-----|--------|------|
| 0x32 | 9 | ~200 | Niski, pełne spektrum, szybki podgląd |
| 0x31 | 3 | ~600 | Średni, fragmenty (tiles) |
| 0x30 | 1 | ~1800 | Pełny, fragmenty (tiles) |

**div** oznacza ile kanałów full-res reprezentuje jeden kanał skompresowany.

#### 4.3.3 Struktura nagłówka spektrum

```
Bajt 0: Długość (0 = 256)
Bajt 1: Typ (0x30/0x31/0x32)
Bajt 2-3: start_ch (little-endian) - KANAŁ POCZĄTKOWY W FULL-RES!
Bajt 4-6: cur_val (big-endian, 3 bajty) - wartość początkowa
Bajt 7+: Zakodowane różnice
```

**KRYTYCZNE:** `start_ch` jest w jednostkach FULL-RES (0-1799), NIE skompresowanych!

```python
start_ch = frame[2] | (frame[3] << 8)  # Little-endian!

# Przeliczenie na indeks skompresowany:
x = start_ch // div
```

#### 4.3.4 Typy punktów (point_type)

Każdy blok danych zaczyna się bajtem kontrolnym:

```python
if b == 0:
    point_type = 4
    points_amount = 1
else:
    point_type = (b & 0xFF) // 64      # Bity 7-6
    points_amount = (b & 0xFF) % 64    # Bity 5-0
```

| point_type | Bity na wartość | Opis |
|------------|-----------------|------|
| 0 | 4 bity | 2 wartości w 1 bajcie (nibble) |
| 1 | 8 bitów | 1 wartość w 1 bajcie (signed) |
| 2 | 12 bitów | 2 wartości w 3 bajtach |
| 3 | 16 bitów | 1 wartość w 2 bajtach (signed LE) |
| 4 | 24 bity | 1 wartość w 3 bajtach (signed LE) |

#### 4.3.5 Dekodowanie point_type = 0 (4-bit nibbles)

Najbardziej kompaktowy format - 2 różnice w 1 bajcie:

```python
elif point_type == 0:
    amount = 0
    while amount < points_amount and pos < limit:
        bytev = frame[pos]
        
        # Górny nibble (bity 7-4)
        diff = (bytev & 0xFF) // 16
        if diff > 7:
            diff -= 16  # Signed: -8 do +7
        cur_val += diff
        bins[x] = cur_val / float(div)  # Normalizacja przez div
        x += 1
        amount += 1

        if amount < points_amount:
            # Dolny nibble (bity 3-0)
            diff = (bytev & 0xFF) % 16
            if diff > 7:
                diff -= 16  # Signed: -8 do +7
            cur_val += diff
            bins[x] = cur_val / float(div)
            x += 1
            amount += 1

        pos += 1
```

**Zakres różnic:** -8 do +7 (4 bity signed)

#### 4.3.6 Dekodowanie point_type = 1 (8-bit signed)

```python
elif point_type == 1:
    amount = 0
    while amount < points_amount and pos < limit:
        diff = frame[pos] & 0xFF
        if diff > 127:
            diff -= 256  # Signed: -128 do +127
        cur_val += diff
        bins[x] = cur_val / float(div)
        x += 1
        amount += 1
        pos += 1
```

**Zakres różnic:** -128 do +127

#### 4.3.7 Dekodowanie point_type = 2 (12-bit pairs)

Dwie 12-bitowe wartości w 3 bajtach:

```
Bajt 0: [b7-b0] = starsze 8 bitów pierwszej wartości
Bajt 1: [b7-b4] = młodsze 4 bity pierwszej | [b3-b0] = starsze 4 bity drugiej
Bajt 2: [b7-b0] = młodsze 8 bitów drugiej wartości
```

```python
elif point_type == 2:
    amount = 0
    while amount < points_amount and pos + 1 < limit:
        b0 = frame[pos]
        b1 = frame[pos + 1]

        # Pierwsza wartość 12-bit
        diff = ((b0 << 4) | ((b1 >> 4) & 0xF)) & 0xFFF
        if diff > 2047:
            diff -= 4096  # Signed: -2048 do +2047
        cur_val += diff
        bins[x] = cur_val / float(div)
        x += 1
        amount += 1
        pos += 2

        if amount < points_amount and pos < limit:
            b2 = frame[pos]
            # Druga wartość 12-bit
            diff = ((b1 & 0xF) << 8) | (b2 & 0xFF)
            if diff > 2047:
                diff -= 4096
            cur_val += diff
            bins[x] = cur_val / float(div)
            x += 1
            amount += 1
            pos += 1
```

**Zakres różnic:** -2048 do +2047

#### 4.3.8 Dekodowanie point_type = 3 (16-bit signed LE)

```python
elif point_type == 3:
    amount = 0
    while amount < points_amount and pos + 1 < limit:
        # Little-endian!
        diff = ((frame[pos + 1] & 0xFF) << 8) | (frame[pos] & 0xFF)
        if diff > 32767:
            diff -= 65536  # Signed: -32768 do +32767
        cur_val += diff
        bins[x] = cur_val / float(div)
        x += 1
        amount += 1
        pos += 2
```

#### 4.3.9 Dekodowanie point_type = 4 (24-bit signed LE)

Używany dla dużych skoków wartości (np. intensywny pik):

```python
elif point_type == 4:
    if pos + 2 < limit:
        # Little-endian 3 bajty
        diff = (frame[pos + 2] << 16) | (frame[pos + 1] << 8) | frame[pos]
        if diff > 8388607:
            diff -= 16777216  # Signed: -8388608 do +8388607
        cur_val += diff
        bins[x] = cur_val / float(div)
        x += 1
        pos += 3
```

#### 4.3.10 Normalizacja przez div

**WAŻNE:** Każda wartość jest dzielona przez `div`:

```python
bins[x] = cur_val / float(div)
```

To wyrównuje wartości między różnymi rozdzielczościami:
- div=9: wartości są 9x wyższe w surowych danych → /9
- div=3: wartości są 3x wyższe → /3
- div=1: bez zmiany

---

## 5. Widżety GUI

### 5.1 SpectrumWidget

**Mapowanie kanałów skompresowanych na full-res:**

```python
def update_spectrum(self, pkt: Dict):
    bins = pkt.get("bins", {})
    div = pkt.get("div", 9)
    
    for ch, val in bins.items():
        ch = int(ch)
        # ch=10 z div=3 → kanały 30, 31, 32
        base_ch = ch * div
        for i in range(div):
            real_ch = base_ch + i
            if 0 <= real_ch < 1800:
                self.spectrum[real_ch] = val
                self.filled_channels.add(real_ch)
```

**Przepływ danych:**
```
Urządzenie          Parser              Widget
─────────────────────────────────────────────────────
start_ch=687 ──────► x = 687//3 = 229 ──► base_ch = 229*3 = 687
(full-res)          bins[229] = val      spectrum[687] = val
                    bins[230] = val      spectrum[690] = val
                    ...                  ...
```

### 5.2 Kalibracja energii

```python
# Bazowa kalibracja dla div=9:
# Pik Cs-137 (662 keV) pojawia się przy kanale ~165
KEV_PER_CHANNEL_BASE = 4.01  # dla div=9

# Dla full-res (1800 kanałów):
# 662 keV / (165 * 9) = 0.446 keV/kanał
def _get_kev_per_channel(self) -> float:
    return KEV_PER_CHANNEL_BASE / 9.0  # ≈ 0.446
```

---

## 6. Kalibracja i przeliczniki

### 6.1 Tabela przeliczników

| Parametr | Wzór | Przykład |
|----------|------|----------|
| keV z kanału | `ch * 0.446` | ch=1485 → 662 keV |
| CPS z raw | `unpack(raw) / 600` | raw=6000 → 10 CPS |
| Dawka z raw | `unpack(raw) / 60000` | raw=60000 → 1 µSv/h |
| Temp z raw | `raw/10 - 100` | raw=1250 → 25°C |

### 6.2 Znane piki referencyjne

| Izotop | Energia | Kanał (full-res) |
|--------|---------|------------------|
| Cs-137 | 662 keV | ~1485 |
| K-40 | 1461 keV | ~3275 (poza zakresem 0-1000 keV) |
| Co-60 | 1173 keV | ~2630 |
| Co-60 | 1332 keV | ~2987 |

---

## 7. Debugowanie

### 7.1 Plik logu

Wszystkie operacje BLE są logowane do `raysid_debug.log`:

```python
def log_to_file(msg: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    _log_file.write(f"{ts} {msg}\n")
    _log_file.flush()
```

### 7.2 Kluczowe logi

```
[SPEC START] type=0x31 buffering 20/256    # Rozpoczęcie buforowania
[SPEC BUFFER] added 20, total=40/256        # Fragment dodany
[SPEC COMPLETE] len=256                     # Pakiet kompletny
[SPEC ✓] type=0x31 bins=85 last_ch=312     # Sukces parsowania
[CPS ✓] cps=12.34 dose=0.001               # Dane CPS
[BATT ✓] level=87% temp=28.5°C             # Status baterii
```

---

## 8. Podsumowanie algorytmów

### 8.1 Schemat przepływu pakietu spektrum

```
BLE Notification (20 bajtów)
        │
        ▼
┌───────────────────────┐
│ Czy length=0 (256B)?  │──► TAK ──► Buforuj fragmenty
└───────────────────────┘              │
        │ NIE                          ▼
        ▼                    ┌─────────────────────┐
   Parsuj bezpośrednio       │ Kompletny pakiet?   │
                             └─────────────────────┘
                                       │ TAK
                                       ▼
                             ┌─────────────────────┐
                             │ _parse_spectrum()   │
                             │                     │
                             │ 1. Odczytaj typ     │
                             │ 2. div = 1/3/9      │
                             │ 3. start_ch (LE)    │
                             │ 4. cur_val (3B BE)  │
                             │ 5. Dekoduj różnice  │
                             │ 6. bins[x] = v/div  │
                             └─────────────────────┘
                                       │
                                       ▼
                             ┌─────────────────────┐
                             │ packet_received     │
                             │ .emit(pkt)          │
                             └─────────────────────┘
                                       │
                                       ▼
                             ┌─────────────────────┐
                             │ update_spectrum()   │
                             │                     │
                             │ for ch in bins:     │
                             │   base = ch * div   │
                             │   for i in range:   │
                             │     spectrum[base+i]│
                             └─────────────────────┘
```

### 8.2 Kompresja różnicowa - wizualizacja

```
Surowe wartości kanałów:  100  102  105  103  101  108  120  118
                           │    │    │    │    │    │    │    │
Różnice (delty):          ─── +2   +3   -2   -2   +7  +12   -2
                           │
Kodowanie:                init  ▲    ▲    ▲    ▲    ▲    ▲    ▲
                          100   │    │    │    │    │    │    │
                                └────┴────┴────┴────┴────┴────┘
                                      point_type=0 (4-bit)
                                      lub point_type=1 (8-bit)
                                      zależnie od wielkości różnic
```

---

## 9. Wersja i data

- **Wersja dokumentacji:** 1.0
- **Data:** 9 stycznia 2026
- **Autor:** Raysid API Team
- **Status:** Złoty wzór - wersja produkcyjna

---

## 10. Szybka ściąga

```python
# === DEKODOWANIE SPEKTRUM ===
div = {0x30: 1, 0x31: 3, 0x32: 9}[ptype]
start_ch = frame[2] | (frame[3] << 8)        # Little-endian!
x = start_ch // div                           # Indeks skompresowany
cur_val = (frame[6] << 16) | (frame[5] << 8) | frame[4]  # Big-endian!

# === POINT TYPES ===
# b == 0       → type=4, amount=1 (24-bit)
# b = 0bTTAAAAAA → type=TT, amount=AAAAAA

# === SIGNED CONVERSION ===
# 4-bit:  if v > 7: v -= 16
# 8-bit:  if v > 127: v -= 256
# 12-bit: if v > 2047: v -= 4096
# 16-bit: if v > 32767: v -= 65536
# 24-bit: if v > 8388607: v -= 16777216

# === NORMALIZACJA ===
bins[x] = cur_val / float(div)

# === MAPOWANIE NA FULL-RES ===
for i in range(div):
    spectrum[ch * div + i] = value
```
