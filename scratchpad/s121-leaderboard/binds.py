import csv, sys, os
ROOT = r"G:\git\Supervive Revival Project"
MEM = os.path.join(ROOT, "tools", "asdump", "out", "binds_members.csv")
TYP = os.path.join(ROOT, "tools", "asdump", "out", "binds_types.csv")

def load():
    with open(MEM, newline='', encoding='utf-8', errors='replace') as f:
        return list(csv.DictReader(f))

def show(names):
    rows = load()
    want = set(n.lower() for n in names)
    for r in rows:
        ot = r['owner_type'] or ''
        if ot.lower().lstrip('fu a') in want or ot.lower() in want or ot.lower().lstrip('f') in want:
            pass
    # simpler: exact match on owner_type with/without leading F/U/A
    for r in rows:
        ot = (r['owner_type'] or '')
        cand = {ot.lower(), ot.lower()[1:] if ot[:1] in 'FUA' else ot.lower()}
        if cand & want:
            print(f"{ot:42s} {r['member_kind']:8s} [{r['member_index']:>3s}] {r['declaration']}")

if __name__ == '__main__':
    show(sys.argv[1:])
