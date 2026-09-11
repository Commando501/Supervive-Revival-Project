import sys
sys.path.insert(0,'scratchpad/s138/laneW2')
from pe import PE
a = PE('dumps/merged13.dump.exe')
b = PE('dumps/merged12.dump.exe')
targets = [
 ('ALokiBotController::Tick', 0x556E9F0),
 ('ALokiBotController::OnPossess', 0x5565470),
 ('ALokiBotController::OnUnPossess', 0x55667F0),
 ('ALokiBotController ctor (ctrl)', 0x554B430),
 ('AController::InitPlayerState (ctrl)', 0x36DEE20),
 ('APawn::SetPlayerState (ctrl)', 0x3BBD9F0),
]
print('%-40s %-12s %-16s %-16s' % ('name','rva','merged13 nz/4096','merged12 nz/4096'))
for n,rva in targets:
    pg = rva & ~0xFFF
    x = a.read(pg,0x1000); y = b.read(pg,0x1000)
    print('%-40s 0x%08X  %5d/4096       %5d/4096' % (n,rva,sum(1 for c in x if c),sum(1 for c in y if c)))
