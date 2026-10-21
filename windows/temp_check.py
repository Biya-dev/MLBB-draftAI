from receiver.protocol import encode_auth, encode_jpeg, FrameDecoder, FrameType
import struct

# 1. Multiple frames per connection
print('Test: 3 frames per connection')
decoder = FrameDecoder()
chunk = encode_auth('tok') + encode_jpeg(b'a') + encode_jpeg(b'bb') + encode_jpeg(b'ccc')
frames = decoder.feed(chunk)
assert len(frames) == 4, f'Expected 4, got {len(frames)}'
assert frames[0][0] == FrameType.AUTH
assert frames[1][0] == FrameType.FRAME
assert frames[2][0] == FrameType.FRAME
assert frames[3][0] == FrameType.FRAME
print('  PASS: 4 frames from single chunk')

# 2. Partial reads (byte-at-a-time)
print('Test: byte-at-a-time delivery')
decoder2 = FrameDecoder()
raw = encode_auth('tok') + encode_jpeg(b'payload')
out = []
for i in range(len(raw)):
    out.extend(decoder2.feed(raw[i:i+1]))
assert len(out) == 2
assert out[0][0] == FrameType.AUTH
assert out[1][0] == FrameType.FRAME
assert out[0][1] == b'tok'
assert out[1][1] == b'payload'
print('  PASS: byte-at-a-time')

# 3. Malformed input / bad magic
print('Test: bad magic')
try:
    decoder3 = FrameDecoder()
    decoder3.feed(b'XXXX\x02\x00\x00\x00\x00')
    assert False, 'Should have raised'
except Exception:
    print('  PASS: bad magic raises error')

# 4. Oversized payload
print('Test: oversized length')
bad = b'MLB1\x02\xff\xff\xff\xff'
try:
    decoder4 = FrameDecoder()
    decoder4.feed(bad)
    assert False, 'Should have raised'
except Exception:
    print('  PASS: oversized length raises error')

# 5. Empty payload
print('Test: empty payload')
raw_empty = encode_jpeg(b'')
decoder5 = FrameDecoder()
frames5 = decoder5.feed(raw_empty)
assert len(frames5) == 1
assert frames5[0][1] == b''
print('  PASS: empty payload')

print('\nAll protocol checks PASSED')