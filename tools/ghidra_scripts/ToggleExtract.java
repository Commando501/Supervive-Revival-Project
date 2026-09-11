// ToggleExtract.java — Ghidra headless GhidraScript (S85).
// Extracts the SUPERVIVE game-feature-toggle READINESS machinery from the saved SuperVive analysis,
// so the assistant can read the decompilation without a live Ghidra GUI.
//
// Anchors (docs/session-85-netcache-chain-diff.md §9):
//   PRIMARY  — LokiPlayerController delegate offsets 0xA98/0xAA8/0xAB8 (OnClientGameFeatureTogglesReady et al):
//              any fn using these as a disp32/imm32 references the readiness delegates; the one that BROADCASTS
//              [this+0xA98] and writes a nearby bool = the readiness SETTER.
//   SECONDARY — committed reflection strings "AttachAudioListenerToHero"/"ELokiGameFeatureToggle"/"CursorCharacterAim".
// For every target it dumps: callers (Xrefs to the entry) + full decompilation. Writes one text file.
//
// Run: analyzeHeadless <projLoc> SuperVive -process SUPERVIVE-deobf.exe -noanalysis \
//        -scriptPath <this dir> -postScript ToggleExtract.java
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.mem.Memory;
import ghidra.util.task.ConsoleTaskMonitor;
import java.io.*;
import java.util.*;

public class ToggleExtract extends GhidraScript {
    PrintWriter out;
    DecompInterface deci;

    public void run() throws Exception {
        String outPath = "G:\\git\\Supervive Revival Project\\dumps\\toggles\\ghidra_toggle_extract.txt";
        out = new PrintWriter(new BufferedWriter(new FileWriter(outPath)));
        out.println("# ToggleExtract — program: " + currentProgram.getName()
                + "  imageBase: " + currentProgram.getImageBase());

        deci = new DecompInterface();
        DecompileOptions opts = new DecompileOptions();
        deci.setOptions(opts);
        deci.openProgram(currentProgram);

        LinkedHashSet<Address> targets = new LinkedHashSet<>();

        // PRIMARY: delegate offsets as little-endian 4-byte patterns (disp32 / imm32).
        long[] offs = { 0xA98L, 0xAA8L, 0xAB8L };
        for (long off : offs) {
            byte[] pat = new byte[] {
                (byte)(off & 0xFF), (byte)((off >> 8) & 0xFF),
                (byte)((off >> 16) & 0xFF), (byte)((off >> 24) & 0xFF)
            };
            addFuncsForBytes(pat, "0x" + Long.toHexString(off) + " (delegate disp32)", targets, 400);
        }

        // SECONDARY: committed reflection strings -> code xrefs (confirm enum / find Get read path).
        for (String s : new String[] { "AttachAudioListenerToHero", "ELokiGameFeatureToggle", "CursorCharacterAim" }) {
            addFuncsForString(s, targets, 12);
        }

        out.println("\n=== TARGET FUNCTIONS: " + targets.size() + " ===");
        for (Address a : targets) {
            Function f = getFunctionContaining(a);
            if (f == null) f = getFunctionAt(a);
            if (f == null) { out.println("(no function at " + a + ")"); continue; }
            dumpFunc(f);
        }
        out.flush();
        out.close();
        deci.dispose();
        println("ToggleExtract wrote " + outPath + " (" + targets.size() + " target functions)");
    }

    void addFuncsForBytes(byte[] pat, String tag, Set<Address> targets, int cap) {
        Memory mem = currentProgram.getMemory();
        Address a = currentProgram.getMinAddress();
        int hits = 0, added = 0;
        while (a != null && hits < cap) {
            Address f = mem.findBytes(a, pat, null, true, monitor);
            if (f == null) break;
            Function fn = getFunctionContaining(f);
            if (fn != null && targets.add(fn.getEntryPoint())) added++;
            a = f.add(1); hits++;
        }
        out.println("// pattern " + tag + ": " + hits + " byte hits, " + added + " new functions");
    }

    void addFuncsForString(String s, Set<Address> targets, int cap) {
        try {
            byte[] pat = s.getBytes("US-ASCII");
            Memory mem = currentProgram.getMemory();
            Address a = currentProgram.getMinAddress();
            int hits = 0;
            while (a != null && hits < cap) {
                Address f = mem.findBytes(a, pat, null, true, monitor);
                if (f == null) break;
                out.println("// string '" + s + "' @ " + f);
                ReferenceIterator ri = currentProgram.getReferenceManager().getReferencesTo(f);
                for (Reference r : ri) {
                    Function fn = getFunctionContaining(r.getFromAddress());
                    if (fn != null) {
                        targets.add(fn.getEntryPoint());
                        out.println("//   code xref from " + r.getFromAddress() + " in " + fn.getName());
                    } else {
                        out.println("//   data xref from " + r.getFromAddress() + " (not in a function)");
                    }
                }
                a = f.add(1); hits++;
            }
        } catch (Exception e) {
            out.println("// string search error for '" + s + "': " + e);
        }
    }

    void dumpFunc(Function f) {
        out.println("\n=================================================================");
        out.println("FUNCTION " + f.getName() + " @ " + f.getEntryPoint()
                + "  size=" + f.getBody().getNumAddresses());
        out.println("-- CALLERS (Xrefs to entry) --");
        ReferenceIterator ri = currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint());
        int c = 0;
        for (Reference r : ri) {
            if (c++ > 50) { out.println("   ...(more)"); break; }
            Function cf = getFunctionContaining(r.getFromAddress());
            out.println("   <- " + r.getFromAddress()
                    + (cf != null ? (" (" + cf.getName() + ")") : " (no func)")
                    + " [" + r.getReferenceType() + "]");
        }
        out.println("-- DECOMPILE --");
        try {
            DecompileResults dr = deci.decompileFunction(f, 90, new ConsoleTaskMonitor());
            if (dr != null && dr.decompileCompleted()) {
                out.println(dr.getDecompiledFunction().getC());
            } else {
                out.println("<decompile failed: " + (dr != null ? dr.getErrorMessage() : "null") + ">");
            }
        } catch (Exception e) {
            out.println("<decompile exception: " + e + ">");
        }
    }
}
