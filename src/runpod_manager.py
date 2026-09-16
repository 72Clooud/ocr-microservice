import logging
import sys

from runpod import RunPodService

logger = logging.getLogger("runpod_cli")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    args = sys.argv[1:]
    cmd = args[0] if args else "status"

    service = RunPodService()

    print("\n--- RunPod Management CLI ---")
    print(f"Current Pod ID:  {service.pod_id}")
    print(f"LLM Base URL:    {service.get_llm_base_url()}\n")

    if cmd == "status":
        status = service.get_status()
        print("Configured:     ", status.get("configured"))
        print("Health Ready:   ", status.get("health_ready"))
        pod_info = status.get("pod_info")
        if pod_info:
            print(f"Status:          {pod_info.get('desiredStatus')}")
            print(f"GPU Cost/hr:     ${pod_info.get('costPerHr')}")
            print(f"Machine ID:      {pod_info.get('machineId')}")
        else:
            print("Pod not found on RunPod (or terminated).")

    elif cmd == "start":
        print("Executing morning startup (starts existing or provisions fresh budget pod)...")
        active_url = service.morning_startup()
        print(f"\n[SUCCESS] Ready! Active OCR endpoint: {active_url}")

    elif cmd == "stop":
        print("Executing evening shutdown...")
        service.evening_shutdown()
        print("[SUCCESS] Pod stop requested.")

    elif cmd == "create":
        print("Provisioning fresh budget pod...")
        pod = service.create_budget_pod()
        service.sync_env_file(pod["id"])
        service.wait_for_ready()
        print(f"[SUCCESS] Created and ready: {service.get_llm_base_url()}")

    elif cmd == "terminate":
        print(f"Terminating pod {service.pod_id}...")
        service.terminate_current_pod()
        print("[SUCCESS] Pod terminated.")

    else:
        print(f"Unknown command: '{cmd}'. Available: start, stop, status, create, terminate")


if __name__ == "__main__":
    main()
