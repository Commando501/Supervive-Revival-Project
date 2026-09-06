@echo off
set "JAVA_HOME=E:\Program Files\Tools\Eclipse Adoptium\jdk-25.0.3.9-hotspot"
call "C:\Users\eastr\Downloads\ghidra_12.1.2_PUBLIC_20260605\ghidra_12.1.2_PUBLIC\support\analyzeHeadless.bat" "G:\git\Supervive Revival Project\Ghidra" SuperVive -process SUPERVIVE-deobf.exe -noanalysis -scriptPath "G:\git\Supervive Revival Project\tools\ghidra_scripts" -postScript FindReadContentBlock.java > C:\Temp\ghidra-rcb.log 2>&1
