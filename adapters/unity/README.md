# Unity adapter

SPDX-License-Identifier: CC0-1.0

`adapters/unity` is a local Unity Package Manager package containing the editor
importer and its batch-mode verification harness. The checked-in
`verify-project` references this package by relative path, so a clone contains
the adapter, the executable entry point, and the project needed to compile it.

The project pins
[Khronos UnityGLTF 2.14.1](https://github.com/KhronosGroup/UnityGLTF/tree/release/2.14.1)
as its `.glb` scripted importer. Package Manager downloads that dependency on
the first run; no Unity project or imported asset lives only on one developer's
machine.

From the repository root on Windows:

```powershell
& 'C:\Program Files\Unity\Hub\Editor\6000.4.11f1\Editor\Unity.exe' `
  -batchmode -nographics -quit `
  -projectPath adapters/unity/verify-project `
  -executeMethod Tessera.TesseraVerify.Run `
  -tesseraRoot (Get-Location).Path `
  -logFile unity-verify.log
```

The command imports every catalog GLB, measures rendered bounds, rebuilds and
checks compound `BoxCollider` collision, proves each traversable aperture is
void, creates prefabs, builds the two-storey layout, verifies its transforms,
and writes `build/unity-verify-report.json`. Any failed assertion exits
non-zero.

Unity still requires an activated editor licence before batch mode will compile
or execute the project. Until a licensed run produces a zero-failure report,
the adapter remains `script-provided-unverified`.
