for a in "$@"; do echo "=== $a"; python tools/strxref/strxref.py func $a 2>&1 | head -14; done
