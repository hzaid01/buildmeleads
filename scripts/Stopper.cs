using System;
using System.Diagnostics;
using System.IO;

namespace LeadGeneratorStopper
{
    internal static class Program
    {
        public static int Main()
        {
            string projectRoot = AppDomain.CurrentDomain.BaseDirectory;
            string batchFile = Path.Combine(projectRoot, "Stop.bat");
            if (!File.Exists(batchFile))
            {
                projectRoot = Directory.GetCurrentDirectory();
                batchFile = Path.Combine(projectRoot, "Stop.bat");
            }
            if (!File.Exists(batchFile))
            {
                Console.Error.WriteLine("Stop.bat was not found beside Stop.exe or in the current directory.");
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
