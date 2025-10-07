import argparse
import os
import subprocess
import time
from datetime import datetime

import schedule


def validate_time(time_str):
    try:
        datetime.strptime(time_str, '%H:%M')
        return time_str
    except ValueError:
        raise argparse.ArgumentTypeError('Time must be in HH:MM format')


def run_script(script_path):
    script_dir = os.path.dirname(script_path)
    if script_dir:
        os.chdir(script_dir)

    try:
        subprocess.run(["bash", script_path], check=True)
        print("Script executed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Script execution failed: {e}")


def main():
    parser = argparse.ArgumentParser(description='Schedule a script to run daily at a specified time')
    parser.add_argument('--time', type=validate_time, required=True,
                        help='Time to run the script (HH:MM format)')
    parser.add_argument('--script', type=str, required=True,
                        help='Path to the script to execute')

    args = parser.parse_args()

    job = schedule.every().day.at(args.time).do(run_script, args.script)
    print(f"Scheduler started. Will run script at {args.time} daily.")

    while True:
        next_run = job.next_run
        print(f"Next run scheduled for: {next_run}", end='\r')
        schedule.run_pending()
        time.sleep(60)


if __name__ == '__main__':
    main()
