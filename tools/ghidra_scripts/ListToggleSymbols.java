// ListToggleSymbols.java — dump any Ghidra symbols/functions/labels whose name hints at the
// game-feature-toggle machinery (RTTI-recovered class names, vftables, or auto-named funcs).
// If RTTI was retained, ULokiGameFeatureToggles / LokiPlayerController toggle members surface here.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.*;
import ghidra.program.model.listing.*;
import java.io.*;

public class ListToggleSymbols extends GhidraScript {
    public void run() throws Exception {
        String outPath = "G:\\git\\Supervive Revival Project\\dumps\\toggles\\ghidra_toggle_symbols.txt";
        PrintWriter out = new PrintWriter(new BufferedWriter(new FileWriter(outPath)));
        String[] needles = { "GameFeatureToggle", "FeatureToggle", "ULokiGameFeatureToggles",
                             "GameFeatureTogglesReady", "ClientGameFeatureToggle", "ToggleReady" };
        SymbolTable st = currentProgram.getSymbolTable();
        SymbolIterator it = st.getAllSymbols(true);
        int n = 0, shown = 0;
        while (it.hasNext()) {
            Symbol s = it.next();
            n++;
            String nm = s.getName();
            for (String needle : needles) {
                if (nm.toLowerCase().contains(needle.toLowerCase())) {
                    Function f = getFunctionContaining(s.getAddress());
                    out.println(s.getAddress() + "  " + s.getSymbolType() + "  " + nm
                            + (f != null ? ("   [in " + f.getName() + "]") : ""));
                    shown++;
                    break;
                }
            }
        }
        out.println("\n# scanned " + n + " symbols, " + shown + " matched.");
        // Also list any FUNCTION whose name is not a raw FUN_ (i.e. Ghidra recovered a real name) and hints toggle.
        out.println("\n# --- named functions containing 'Toggle' or 'Feature' (non-FUN_) ---");
        FunctionIterator fit = currentProgram.getFunctionManager().getFunctions(true);
        int fn = 0;
        while (fit.hasNext()) {
            Function f = fit.next();
            String nm = f.getName();
            if (!nm.startsWith("FUN_") && (nm.toLowerCase().contains("toggle") || nm.toLowerCase().contains("feature"))) {
                out.println(f.getEntryPoint() + "  " + nm);
                fn++;
            }
        }
        out.println("# " + fn + " named toggle/feature functions.");
        out.close();
        println("ListToggleSymbols wrote " + outPath + " (" + shown + " symbol matches, " + fn + " named funcs)");
    }
}
