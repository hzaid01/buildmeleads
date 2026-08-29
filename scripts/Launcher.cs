using System;
using System.Diagnostics;
using System.IO;

namespace LeadGeneratorLauncher
{
    internal static class Program
    {
        public static int Main()
        {
            string projectRoot = AppDomain.CurrentDomain.BaseDirectory;
            string batchFile = Path.Combine(projectRoot, "Launch.bat");
            if (!File.Exists(batchFile))
            {
                // Published build is copied to the project root; development builds live under scripts/bin.
                projectRoot = Directory.GetCurrentDirectory();
                batchFile = Path.Combine(projectRoot, "Launch.bat");
            }
            if (!File.Exists(batchFile))
            {
                Console.Error.WriteLine("Launch.bat was not found beside Launch.exe or in the current directory.");
                return 1;
            }
            using (Process process = Process.Start(new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = string.Format("/d /c \"\"{0}\"\"", batchFile),
                WorkingDirectory = projectRoot,
                UseShellExecute = false,
                CreateNoWindow = false
            }))
            {
                process.WaitForExit();
                return process.ExitCode;
            }
        }
    }
}
