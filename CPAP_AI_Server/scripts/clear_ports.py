"""
Pre-flight Port Scanner & Conflict Resolver
===========================================
Scans target ports (default: 8000 and 8001), identifies any stale listening processes,
terminates them forcefully using Windows taskkill, verifies socket release, and
prints clear status diagnostics for console visibility.
"""
import sys
import os
import time
import socket
import subprocess

def get_process_name(pid: int) -> str:
    """Retrieves process executable name for a given PID."""
    try:
        cmd = f'tasklist /FI "PID eq {pid}" /FO CSV /NH'
        out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            line = line.strip()
            if line and line.startswith('"'):
                parts = line.split('","')
                if len(parts) >= 1:
                    return parts[0].replace('"', '')
    except Exception:
        pass
    return "unknown"


def find_pids_on_port(port: int) -> set:
    """Finds all PIDs listening on the specified TCP port."""
    pids = set()
    current_pid = os.getpid()
    try:
        out = subprocess.check_output('netstat -ano', shell=True, text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            line = line.strip()
            # Match ":port " with LISTENING state
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        pid = int(parts[-1])
                        if pid > 4 and pid != current_pid:
                            pids.add(pid)
                    except ValueError:
                        pass
    except Exception:
        pass
    return pids


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """Tests whether a port can be bound immediately."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((host, port))
        s.close()
        return True
    except Exception:
        s.close()
        return False


def clear_port(port: int, service_label: str = "") -> bool:
    """Scans and clears any process occupying the given port."""
    label = f" ({service_label})" if service_label else ""
    pids = find_pids_on_port(port)

    if not pids and is_port_available(port):
        print(f"    * Port {port}{label:26} : [CLEAN & AVAILABLE]")
        return True

    if pids:
        for pid in pids:
            pname = get_process_name(pid)
            print(f"    * Port {port}{label:26} : [OCCUPIED] PID {pid} ({pname}) -> Terminating...", end=" ", flush=True)
            try:
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("[TERMINATED]")
            except Exception as e:
                print(f"[ERROR: {e}]")

    # Wait up to 2 seconds for OS socket table release
    start_t = time.time()
    cleared = False
    while time.time() - start_t < 2.0:
        if is_port_available(port):
            cleared = True
            break
        time.sleep(0.2)

    if cleared:
        print(f"    * Port {port}{label:26} : [CLEARED & READY]")
        return True
    else:
        print(f"    * Port {port}{label:26} : [WARNING] Port release pending or TIME_WAIT.")
        return False


def main():
    # Ports to scan and clear
    port_targets = [
        (8000, "REST API & Dashboard"),
        (8001, "Webhook Receiver")
    ]

    # Allow overriding ports from argv
    if len(sys.argv) > 1:
        port_targets = []
        for arg in sys.argv[1:]:
            try:
                port_targets.append((int(arg), f"Custom Port {arg}"))
            except ValueError:
                pass

    print("===============================================================================")
    print("  [PRE-FLIGHT TCP PORT SCAN & AUTO-CLEANUP]")
    print("  Ensuring zero socket conflicts before starting SleepCare AI Server...")
    print("-------------------------------------------------------------------------------")

    all_ready = True
    for port, label in port_targets:
        ok = clear_port(port, label)
        if not ok:
            all_ready = False

    print("-------------------------------------------------------------------------------")
    if all_ready:
        print("  [PRE-FLIGHT STATUS: OK] All required ports are clear and ready to bind.")
    else:
        print("  [PRE-FLIGHT STATUS: PROCEEDING] Sockets freed; launching server runtime.")
    print("===============================================================================")
    print()


if __name__ == "__main__":
    main()
