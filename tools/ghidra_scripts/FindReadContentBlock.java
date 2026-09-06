// FindReadContentBlock.java — S87: locate UActorChannel::ReadContentBlockHeader in the SUPERVIVE client
// via the committed LogNetTraffic string "sub-object class" (from "Unable to read sub-object class"),
// decompile it, and list its callees (so the nested subobject-deserialization — where the client reads the
// ~10-11 EXTRA bits that desync the stub's stock subobject content block — can be followed). Writes one file.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.pcode.*;
import ghidra.util.task.ConsoleTaskMonitor;
import java.io.*;
import java.util.*;

public class FindReadContentBlock extends GhidraScript {
    static byte[] utf16le(String s) {
        byte[] b = new byte[s.length()*2];
        for (int i=0;i<s.length();i++){ b[i*2]=(byte)s.charAt(i); b[i*2+1]=0; }
        return b;
    }
    public void run() throws Exception {
        String outPath = "G:\\git\\Supervive Revival Project\\dumps\\toggles\\ghidra_readcontentblock.txt";
        PrintWriter out = new PrintWriter(new BufferedWriter(new FileWriter(outPath)));
        DecompInterface deci = new DecompInterface();
        DecompileOptions opts = new DecompileOptions();
        deci.setOptions(opts);
        deci.openProgram(currentProgram);

        // Distinctive substrings of ReadContentBlockHeader-only log strings.
        String[] needles = {"sub-object class", "Instantiating sub-object", "stably named bit"};
        LinkedHashSet<Address> funcs = new LinkedHashSet<>();
        for (String needle : needles) {
            byte[] pat = utf16le(needle);
            out.println("// === searching UTF-16LE '"+needle+"' ===");
            Address a = currentProgram.getMinAddress();
            int hits=0;
            while (a != null && hits < 12) {
                Address found = find(a, pat);
                if (found == null) break;
                hits++;
                out.println("//   hit @ " + found);
                boolean any=false;
                for (Reference r : currentProgram.getReferenceManager().getReferencesTo(found)) {
                    any=true;
                    Function f = getFunctionContaining(r.getFromAddress());
                    out.println("//     xref from " + r.getFromAddress() + (f!=null?(" in "+f.getName()+" @ "+f.getEntryPoint()):" (no func)"));
                    if (f != null) funcs.add(f.getEntryPoint());
                }
                if (!any) out.println("//     (no xrefs — may need manual LEA scan)");
                a = found.add(2);
            }
            if (hits==0) out.println("//   NOT FOUND (string may be encrypted/uncommitted)");
        }

        out.println("\n=== DECOMPILING "+funcs.size()+" candidate function(s) + their callees ===");
        LinkedHashSet<Address> callees = new LinkedHashSet<>();
        for (Address fa : funcs) {
            Function f = getFunctionContaining(fa);
            if (f==null) continue;
            out.println("\n================================================================");
            out.println("FUNCTION "+f.getName()+" @ "+f.getEntryPoint());
            DecompileResults dr = deci.decompileFunction(f, 180, new ConsoleTaskMonitor());
            if (dr!=null && dr.decompileCompleted()) {
                out.println(dr.getDecompiledFunction().getC());
                // collect callees for a follow-up pass
                for (Function c : f.getCalledFunctions(new ConsoleTaskMonitor())) callees.add(c.getEntryPoint());
            } else {
                out.println("<decompile failed: "+(dr!=null?dr.getErrorMessage():"null")+">");
            }
        }

        out.println("\n=== CALLEES of the above (entry points, for a targeted follow-up decompile) ===");
        for (Address ca : callees) {
            Function c = getFunctionContaining(ca);
            if (c!=null) out.println("   callee "+c.getName()+" @ "+c.getEntryPoint());
        }
        out.close();
        deci.dispose();
        println("FindReadContentBlock wrote "+outPath+" ("+funcs.size()+" funcs, "+callees.size()+" callees)");
    }
}
