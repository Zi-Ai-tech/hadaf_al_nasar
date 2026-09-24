import subprocess
import requests

def check_vulnerabilities():
    # Check for known vulnerabilities
    result = subprocess.run(['safety', 'check'], capture_output=True, text=True)
    print("Security vulnerabilities:", result.stdout)
    
    # Check for outdated packages
    result = subprocess.run(['pip', 'list', '--outdated'], capture_output=True, text=True)
    print("Outdated packages:", result.stdout)

if __name__ == '__main__':
    check_vulnerabilities()