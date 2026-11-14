"""Bounded discovery at the known modem IP and configured default gateways."""
import json
import os
import subprocess
from .client import Device,DeviceError,compatible,validate_router

def default_gateways():
    if os.name!='nt':return []
    try:
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
            "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop).NextHop | ConvertTo-Json -Compress"],
            capture_output=True,check=True,timeout=8,text=True)
        data=json.loads(result.stdout)
        return data if isinstance(data,list) else [data] if isinstance(data,str) else []
    except (OSError,ValueError,subprocess.SubprocessError):return []

def discover(device_factory=Device,route_reader=default_gateways):
    candidates=['192.168.0.254',*route_reader()][:5];seen=set()
    for candidate in candidates:
        try:address=validate_router(candidate)
        except (ValueError,AttributeError):continue
        if address in seen:continue
        seen.add(address)
        try:
            device=device_factory(address)
            if compatible(device.identity()):return device
        except DeviceError:continue
    raise DeviceError('No verified P19H found at the known IP/default gateways; use --router with its private IPv4')
