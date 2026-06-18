import subprocess
from pathlib import Path

def main():
    root = Path(__file__).resolve().parents[2]
    # Clone VTM into the project root directory
    vtm_dir = root / "VVCSoftware_VTM"
    
    if not vtm_dir.exists():
        print("Cloning VTM 18.0...")
        subprocess.run(["git", "clone", "--depth", "1", "--branch", "VTM-18.0", "https://vcgit.hhi.fraunhofer.de/jvet/VVCSoftware_VTM.git", str(vtm_dir)], check=True)
    else:
        print("VTM directory already exists.")

    build_dir = vtm_dir / "build"
    build_dir.mkdir(exist_ok=True)
    
    print("Running CMake...")
    subprocess.run(["cmake", ".."], cwd=str(build_dir), check=True)
    
    print("Building Release...")
    subprocess.run(["cmake", "--build", ".", "--config", "Release", "-j", "8"], cwd=str(build_dir), check=True)
    
    # Copy binaries to binaries/vtm
    bin_out = root / "binaries" / "vtm"
    bin_out.mkdir(parents=True, exist_ok=True)
    
    import shutil
    # Locate and copy the built executable files
    for exe_name in ["EncoderApp.exe", "DecoderApp.exe"]:
        found = list(vtm_dir.rglob(exe_name))
        if found:
            for f in found:
                if "Release" in str(f):
                    print(f"Copying {f} to {bin_out}")
                    shutil.copy(f, bin_out / exe_name)
                    break
        else:
            print(f"Warning: {exe_name} not found!")

if __name__ == "__main__":
    main()
