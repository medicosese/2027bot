import os
import sys
import subprocess
import argparse

KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ec2_key.pem")
BOT_DIR = os.path.dirname(os.path.abspath(__file__))

def deploy(host_ip: str, user: str = "ubuntu"):
    print("="*75)
    print(f"DEPLOYING TAMA LIVE BOT TO AWS EC2 ({user}@{host_ip})")
    print("="*75)
    
    # 1. Test SSH connection
    ssh_opts = ["-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", "-i", KEY_PATH]
    
    print("\n1. Testing SSH connectivity...")
    test_cmd = ["ssh"] + ssh_opts + [f"{user}@{host_ip}", "echo 'SSH_SUCCESS'"]
    res = subprocess.run(test_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAILED to connect to {host_ip}: {res.stderr.strip()}")
        print("\nPlease check that:")
        print("  1. The AWS EC2 instance is currently RUNNING in AWS Management Console.")
        print("  2. The Public IPv4 address is correct (EC2 public IP changes when stopped/started).")
        print("  3. Security Group inbound rule allows Port 22 (SSH) from your IP.")
        return False
        
    print("SSH connection verified successfully!")
    
    # 2. Create remote directory
    print("\n2. Creating remote directory /home/ubuntu/tama_live_bot/...")
    mkdir_cmd = ["ssh"] + ssh_opts + [f"{user}@{host_ip}", "mkdir -p /home/ubuntu/tama_live_bot"]
    subprocess.run(mkdir_cmd, check=True)
    
    # 3. Copy files via SCP
    print("\n3. Syncing bot files to EC2...")
    files_to_sync = [
        "config.py",
        "binance_trade_bridge.py",
        "state_manager.py",
        "tama_engine.py",
        "dashboard.py",
        "watchdog_runner.py",
        "export_live_logs.py",
        "requirements.txt",
        "start_bot.sh",
        "stop_bot.sh"
    ]
    
    for f in files_to_sync:
        local_f = os.path.join(BOT_DIR, f)
        if os.path.exists(local_f):
            scp_cmd = ["scp"] + ssh_opts + [local_f, f"{user}@{host_ip}:/home/ubuntu/tama_live_bot/{f}"]
            subprocess.run(scp_cmd, check=True)
            print(f"  Uploaded: {f}")
            
    # 4. Make scripts executable and launch tmux
    print("\n4. Making scripts executable and launching tmux session 'tama_bot'...")
    remote_cmd = (
        "cd /home/ubuntu/tama_live_bot && "
        "chmod +x start_bot.sh stop_bot.sh && "
        "sudo apt-get update -y > /dev/null && sudo apt-get install -y tmux python3-venv > /dev/null && "
        "./start_bot.sh"
    )
    launch_cmd = ["ssh"] + ssh_opts + [f"{user}@{host_ip}", remote_cmd]
    res_launch = subprocess.run(launch_cmd, capture_output=True, text=True)
    print(res_launch.stdout)
    
    # 5. Check tmux status
    print("\n5. Verifying running tmux session...")
    check_tmux = ["ssh"] + ssh_opts + [f"{user}@{host_ip}", "tmux ls"]
    res_tmux = subprocess.run(check_tmux, capture_output=True, text=True)
    print(res_tmux.stdout)
    
    print("="*75)
    print("DEPLOYMENT COMPLETE!")
    print(f"To monitor your bot live in terminal, run:")
    print(f"  ssh -i \"{KEY_PATH}\" {user}@{host_ip} \"tmux attach -t tama_bot\"")
    print("="*75)
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy TAMA live bot to AWS EC2")
    parser.add_argument("--host", default="56.228.28.139", help="EC2 Public IPv4 address")
    parser.add_argument("--user", default="ubuntu", help="SSH username (default: ubuntu)")
    args = parser.parse_args()
    
    deploy(args.host, args.user)
