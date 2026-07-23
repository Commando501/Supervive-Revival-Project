// DecompileByRefs.java — decompile the functions that reference specific data anchors (the committed
// ULokiGameFeatureToggles::Get error format strings + the readiness accessor name strings), to recover
// Get()'s ready-flag/storage logic and the OnRep->ready chain. Writes one text file.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.util.task.ConsoleTaskMonitor;
import java.io.*;
import java.util.*;

public class DecompileByRefs extends GhidraScript {
    public void run() throws Exception {
        String outPath = "G:\\git\\Supervive Revival Project\\dumps\\toggles\\ghidra_get_decompile.txt";
        PrintWriter out = new PrintWriter(new BufferedWriter(new FileWriter(outPath)));
        DecompInterface deci = new DecompInterface();
        deci.openProgram(currentProgram);

        // Anchor data addresses (from ghidra_toggle_symbols.txt).
        long[] anchors = {
            0x7ff6b7b1c3e8L, 0x7ff6b7b1c410L, 0x7ff6b7b1c4d0L, 0x7ff6b7b1c4f0L,
            0x7ff6b7b1c568L, 0x7ff6b7b1c590L, 0x7ff6b7b1c608L, 0x7ff6b7b1c630L, // Get %s error fmt + PTRs
            0x7ff6b7b1c748L,   // ULokiGameFeatureToggles::GetCVar
            0x7ff6b7970fa0L,   // GetFeatureTogglesReady
            0x7ff6b7971190L,   // GetFeatureToggleValue
            0x7ff6b7971428L,   // GetFeatureToggleWithDefaultFallback
            0x7ff6b7a57010L    // OnRep_GameFeatureToggles (reflection name)
        };
        LinkedHashSet<Address> targets = new LinkedHashSet<>();
        for (long a : anchors) {
            Address da = toAddr(a);
            out.println("// anchor " + da);
            ReferenceIterator ri = currentProgram.getReferenceManager().getReferencesTo(da);
            for (Reference r : ri) {
                Function f = getFunctionContaining(r.getFromAddress());
                if (f != null) { targets.add(f.getEntryPoint()); out.println("//   code xref from " + r.getFromAddress() + " in " + f.getName()); }
                else out.println("//   data xref from " + r.getFromAddress());
            }
        }

        out.println("\n=== DECOMPILING " + targets.size() + " referencing functions ===");
        for (Address a : targets) {
            Function f = getFunctionContaining(a);
            if (f == null) continue;
            out.println("\n=================================================================");
            out.println("FUNCTION " + f.getName() + " @ " + f.getEntryPoint());
            out.println("-- CALLERS --");
            int c = 0;
            for (Reference r : currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint())) {
                if (c++ > 40) { out.println("  ...(more)"); break; }
                Function cf = getFunctionContaining(r.getFromAddress());
                out.println("   <- " + r.getFromAddress() + (cf != null ? (" (" + cf.getName() + ")") : "") );
            }
            out.println("-- DECOMPILE --");
            DecompileResults dr = deci.decompileFunction(f, 90, new ConsoleTaskMonitor());
            out.println(dr != null && dr.decompileCompleted() ? dr.getDecompiledFunction().getC()
                    : "<decompile failed: " + (dr != null ? dr.getErrorMessage() : "null") + ">");
        }
        out.close();
        deci.dispose();
        println("DecompileByRefs wrote " + outPath + " (" + targets.size() + " functions)");
    }
}
