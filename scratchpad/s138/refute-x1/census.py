import sys
sys.path.insert(0,'scratchpad/s138/refute-x1')
from pg import Img
for p in ['dumps/merged13.dump.exe','dumps/merged12.dump.exe','dumps/merged10.dump.exe','dumps/merged2.dump.exe']:
    im=Img(p)
    lit,tot=im.text_page_census()
    print(f"{p}: {lit}/{tot} = {100.0*lit/tot:.2f}%")
