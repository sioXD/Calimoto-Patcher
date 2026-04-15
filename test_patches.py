#!/usr/bin/env python3
"""
Calimoto APK Patcher - Multi-Patch Test Suite
Tests different patch combinations and creates test APKs

Features:
- Tests all individual patches
- Tests all patch combinations
- Creates APKs in testresults/ directory
- Named as patch_0.apk, patch_0_1.apk, patch_0_1_2.apk, etc.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from itertools import combinations
from datetime import datetime
import re

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Color codes
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class PatchTestSuite:
    """Test suite for patch combinations"""

    PATCHES = ['patch_0_navigation_unlock', 'patch_1_xml_config', 'patch_2_offline_maps',
               'patch_3_navigation_premium_check', 'patch_4_navigation_premium_check_2']

    def __init__(self, script_dir: Path):
        self.script_dir = script_dir
        self.apk_path = script_dir / "calimoto.apk"
        self.patcher_script = script_dir / "calimoto_patcher.py"
        self.results_dir = script_dir / "testresults"
        self.work_dir = script_dir / "calimoto_work"
        self.apk_backup = script_dir / "calimoto_backup.apk"

        # Import patcher modules
        try:
            from calimoto_patcher import PatchManager, APKWorker
            self.PatchManager = PatchManager
            self.APKWorker = APKWorker
            self.patcher_available = True
        except ImportError as e:
            print(f"{Colors.YELLOW}Warning: Patcher modules not available: {e}{Colors.RESET}")
            self.patcher_available = False

    def setup(self) -> bool:
        """Setup test environment"""
        print(f"{Colors.BLUE}{Colors.BOLD}Setting up test environment...{Colors.RESET}\n")

        # Check files exist
        if not self.apk_path.exists():
            print(f"{Colors.RED}[FAIL] Error: calimoto.apk not found{Colors.RESET}")
            return False

        # Create testresults directory
        self.results_dir.mkdir(exist_ok=True)
        print(f"{Colors.GREEN}[OK] testresults/ directory ready{Colors.RESET}")

        if not self.patcher_available:
            print(f"{Colors.YELLOW}[WARN] Patcher modules not fully available{Colors.RESET}")

        print()
        return True

    def get_patch_combinations(self) -> list:
        """Generate all patch combinations"""
        combinations_list = []

        # Individual patches
        for patch in self.PATCHES:
            combinations_list.append([patch])

        # All combinations of 2+
        for r in range(2, len(self.PATCHES) + 1):
            for combo in combinations(self.PATCHES, r):
                combinations_list.append(list(combo))

        return combinations_list

    def get_apk_name(self, patches: list) -> str:
        """Generate APK filename from patch list"""
        # Extract patch numbers (patch_0, patch_1, etc.)
        patch_numbers = []
        for patch in patches:
            num = patch.split('_')[1]  # Extract "0" from "patch_0_..."
            patch_numbers.append(num)

        patch_numbers.sort(key=int)
        filename = f"patch_{'_'.join(patch_numbers)}.apk"
        return filename

    def run_patch_combination(self, patches: list) -> bool:
        """Run patcher with specific patch combination"""
        apk_name = self.get_apk_name(patches)
        output_apk = self.results_dir / apk_name

        print(f"{Colors.CYAN}Testing: {' + '.join([p.split('_')[1] for p in patches])}{Colors.RESET}")
        print(f"  Output: {apk_name}")

        try:
            # Clean old work directory
            if self.work_dir.exists():
                shutil.rmtree(self.work_dir, ignore_errors=True)

            # Create a copy of original APK for patching
            work_apk = self.script_dir / f"work_{apk_name}"
            shutil.copy2(self.apk_path, work_apk)

            print(f"  Status: {Colors.YELLOW}Decompiling...{Colors.RESET}", end='', flush=True)

            # Import here to avoid issues if modules aren't available
            from calimoto_patcher import APKWorker

            # Get paths (stub for now - would need actual tool paths)
            apktool_path = self._find_apktool()
            apksigner_path = self._find_apksigner()

            if not apktool_path or not apksigner_path:
                print(f" {Colors.RED}[SKIP - Tools not found]{Colors.RESET}")
                work_apk.unlink(missing_ok=True)
                return False

            worker = APKWorker(apktool_path, apksigner_path)

            # Decompile
            success, msg = worker.decompile(str(work_apk), str(self.work_dir))
            if not success:
                print(f" {Colors.RED}[FAIL]{Colors.RESET}")
                work_apk.unlink(missing_ok=True)
                return False

            print(f" {Colors.GREEN}[OK]{Colors.RESET}")
            print(f"  Status: {Colors.YELLOW}Patching...{Colors.RESET}", end='', flush=True)

            # Apply patches
            from calimoto_patcher import PatchManager
            patcher = PatchManager(self.work_dir)

            for patch_id in patches:
                success, msg = patcher.apply_patch(patch_id)
                if not success and "SKIP" not in msg:
                    print(f" {Colors.RED}[FAIL: {patch_id}]{Colors.RESET}")
                    work_apk.unlink(missing_ok=True)
                    return False

            print(f" {Colors.GREEN}[OK]{Colors.RESET}")
            print(f"  Status: {Colors.YELLOW}Building...{Colors.RESET}", end='', flush=True)

            # Rebuild APK
            final_apk = self.results_dir / apk_name
            success, msg = worker.rebuild(str(self.work_dir), str(final_apk))
            if not success:
                print(f" {Colors.RED}[FAIL]{Colors.RESET}")
                work_apk.unlink(missing_ok=True)
                return False

            print(f" {Colors.GREEN}[OK]{Colors.RESET}")

            # Sign APK
            print(f"  Status: {Colors.YELLOW}Signing...{Colors.RESET}", end='', flush=True)

            keystore_path = self.script_dir / "calimoto.keystore"
            if not keystore_path.exists():
                print(f" {Colors.YELLOW}[SKIP - No keystore]{Colors.RESET}")
            else:
                # Read keystore password from env config
                keystore_password = self._get_keystore_password()
                if not keystore_password:
                    print(f" {Colors.YELLOW}[SKIP - No password]{Colors.RESET}")
                else:
                    success, msg = worker.sign(str(final_apk), str(keystore_path), "myalias", keystore_password)
                    if not success:
                        print(f" {Colors.YELLOW}[WARN: {msg}]{Colors.RESET}")
                    else:
                        print(f" {Colors.GREEN}[OK]{Colors.RESET}")

            # Verify APK was created
            if final_apk.exists():
                size_mb = final_apk.stat().st_size / (1024 * 1024)
                print(f"  Patches: {', '.join([p.split('_')[1] for p in patches])}")
                print(f"  Size: {size_mb:.2f} MB")
                print(f"  Result: {Colors.GREEN}[OK]{Colors.RESET}")
                work_apk.unlink(missing_ok=True)
                return True
            else:
                print(f" {Colors.RED}[FAIL - APK not created]{Colors.RESET}")
                work_apk.unlink(missing_ok=True)
                return False

        except Exception as e:
            print(f" {Colors.RED}[ERROR: {str(e)[:50]}]{Colors.RESET}")
            work_apk.unlink(missing_ok=True)
            return False
        finally:
            # Cleanup
            if self.work_dir.exists():
                shutil.rmtree(self.work_dir, ignore_errors=True)

    def _find_apktool(self) -> str:
        """Find apktool"""
        try:
            result = subprocess.run(['where', 'apktool'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except:
            pass
        return None

    def _find_apksigner(self) -> str:
        """Find apksigner"""
        try:
            result = subprocess.run(['where', 'apksigner'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except:
            pass
        return None

    def _get_keystore_password(self) -> str:
        """Get keystore password from env config"""
        try:
            env_file = self.script_dir / '.calimoto-patcher.env'
            if env_file.exists():
                import json
                with open(env_file, 'r') as f:
                    config = json.load(f)
                return config.get('keystore_password')
        except:
            pass
        return None


    def run_test_suite(self):
        """Run complete test suite"""
        print(f"{Colors.BLUE}{Colors.BOLD}{'='*70}")
        print(f"Calimoto APK Patcher - Test Suite")
        print(f"{'='*70}{Colors.RESET}\n")

        # Setup
        if not self.setup():
            return

        # Get all combinations
        combinations_list = self.get_patch_combinations()
        total = len(combinations_list)

        print(f"{Colors.BOLD}Test Configuration:{Colors.RESET}")
        print(f"  Total Patches Available: {len(self.PATCHES)}")
        print(f"  Total Combinations: {total}")
        print(f"  Output Directory: testresults/\n")

        print(f"{Colors.BOLD}Starting Tests...{Colors.RESET}\n")

        passed = 0
        failed = 0

        for i, patches in enumerate(combinations_list, 1):
            print(f"{Colors.BOLD}[{i}/{total}]{Colors.RESET} ", end='')

            if self.run_patch_combination(patches):
                passed += 1
            else:
                failed += 1
            print()

        # Summary
        print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*70}")
        print(f"Test Summary{Colors.RESET}")
        print(f"{'='*70}")
        print(f"Total Tests:  {total}")
        print(f"Passed:       {Colors.GREEN}{passed}{Colors.RESET}")
        print(f"Failed:       {Colors.RED}{failed}{Colors.RESET}")

        if total > 0:
            print(f"Success Rate: {Colors.BOLD}{(passed/total)*100:.1f}%{Colors.RESET}")

        if failed == 0 and passed > 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}[OK] All test APKs created successfully!{Colors.RESET}")
            print(f"Results saved in: testresults/\n")
        else:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}[INFO] Some tests skipped or failed.{Colors.RESET}\n")

    def list_test_results(self):
        """List all generated test APKs"""
        if not self.results_dir.exists():
            print(f"{Colors.YELLOW}No test results directory found{Colors.RESET}")
            return

        apks = list(self.results_dir.glob("*.apk"))
        if not apks:
            print(f"{Colors.YELLOW}No APKs generated yet{Colors.RESET}")
            return

        print(f"{Colors.CYAN}{Colors.BOLD}Generated Test APKs:{Colors.RESET}")
        print(f"{'='*70}")

        for apk in sorted(apks):
            size_mb = apk.stat().st_size / (1024 * 1024)
            modified = datetime.fromtimestamp(apk.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            print(f"  {apk.name:30s} {size_mb:8.2f} MB  ({modified})")

        print(f"{'='*70}")


def main():
    """Main entry point"""
    script_dir = Path(__file__).parent

    suite = PatchTestSuite(script_dir)

    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        suite.list_test_results()
    else:
        suite.run_test_suite()


if __name__ == '__main__':
    main()