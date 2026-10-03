const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const output = path.join(root, "build", "native");

if (process.platform !== "win32") {
  fs.mkdirSync(output, { recursive: true });
  fs.writeFileSync(
    path.join(output, "NATIVE-WINDOWS-APP-NOT-BUILT.txt"),
    "The WinUI dashboard is built on Windows only.\n",
  );
  console.log("Skipping the WinUI dashboard build outside Windows.");
  process.exit(0);
}

fs.rmSync(output, { recursive: true, force: true });
const result = spawnSync(
  "dotnet",
  [
    "publish",
    path.join(root, "Aria.Native", "Aria.Native.csproj"),
    "--configuration",
    "Release",
    "--runtime",
    "win-x64",
    "--self-contained",
    "true",
    "--output",
    output,
  ],
  { cwd: root, stdio: "inherit", windowsHide: true },
);

if (result.error) {
  console.error(`Could not build the native dashboard: ${result.error.message}`);
  process.exit(1);
}
if (result.status !== 0) process.exit(result.status ?? 1);

for (const asset of ["Aria.Native.exe", "aria.ico", "aria.png"]) {
  const assetPath = path.join(output, asset);
  if (!fs.existsSync(assetPath)) {
    console.error(`The native dashboard publish is missing ${asset}.`);
    process.exit(1);
  }
}

console.log("Native dashboard, application icon, and loading image are ready.");
