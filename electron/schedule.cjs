"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

function remember(pngPath, line) {
  try {
    fs.appendFileSync(path.join(path.dirname(pngPath), "set.log"), `${line}\n`, "utf8");
  } catch {
    /* the wallpaper result still has to be returned */
  }
}

function runPowerShell(script) {
  const body = `$ProgressPreference = 'SilentlyContinue'\n${script}`;
  const encoded = Buffer.from(script, "utf16le").toString("base64");
  return new Promise((resolve) => {
    const child = spawn(
      "powershell.exe",
      ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
      { windowsHide: true },
    );
    let out = "";
    let err = "";
    child.stdout.on("data", (chunk) => { out += chunk.toString("utf8"); });
    child.stderr.on("data", (chunk) => { err += chunk.toString("utf8"); });
    child.on("close", (code) => resolve({ code: code ?? 1, out, err }));
  });
}

function psQuote(text) {
  return `'${String(text).replaceAll("'", "''")}'`;
}

function taskStatus(name) {
  const script = `
$ErrorActionPreference = 'Stop'
$task = Get-ScheduledTask -TaskName ${psQuote(name)} -ErrorAction SilentlyContinue
if (-not $task) { @{ installed = $false } | ConvertTo-Json -Compress; exit 0 }
$info = Get-ScheduledTaskInfo -TaskName ${psQuote(name)}
@{
  installed = $true
  name = $task.TaskName
  state = [string]$task.State
  next = if ($info.NextRunTime) { $info.NextRunTime.ToString('yyyy-MM-dd HH:mm') } else { '' }
} | ConvertTo-Json -Compress
`;
  return runPowerShell(script).then(({ code, out, err }) => {
    if (code !== 0) return { installed: false, error: err.trim() || "查询计划任务失败" };
    try {
      return JSON.parse(out.trim());
    } catch {
      return { installed: false, error: "计划任务状态无法解析" };
    }
  });
}

function taskInstall(name, dailyTime, command, apply) {
  const args = String((command && command.args) || "").trim();
  const action = args
    ? `New-ScheduledTaskAction -Execute ${psQuote(command.execute)} -Argument ${psQuote(args)}`
    : `New-ScheduledTaskAction -Execute ${psQuote(command.execute)}`;
  const applyArgs = String((apply && apply.args) || "").trim();
  const applyAction = apply
    ? `New-ScheduledTaskAction -Execute ${psQuote(apply.execute)} -Argument ${psQuote(applyArgs)}`
    : "";
  const unlockName = `${name}Unlock`;
  const unlockScript = apply ? `
$apply = ${applyAction}
$stateClass = Get-CimClass -Namespace Root/Microsoft/Windows/TaskScheduler -ClassName MSFT_TaskSessionStateChangeTrigger
$unlock = New-CimInstance -CimClass $stateClass -ClientOnly
$unlock.StateChange = 8
$unlock.UserId = "$env:USERDOMAIN\\$env:USERNAME"
$unlock.Delay = 'PT15S'
Register-ScheduledTask -TaskName ${psQuote(unlockName)} -Action $apply -Trigger $unlock -Principal $principal -Settings $settings -Force | Out-Null
` : "";
  const script = `
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$action = ${action}
$trigger = New-ScheduledTaskTrigger -Daily -At ${psQuote(dailyTime)}
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName ${psQuote(name)} -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
${unlockScript}
'ok'
`;
  return runPowerShell(script).then(({ code, out, err }) => {
    if (code !== 0 || !out.includes("ok")) {
      return { ok: false, error: (err || out).trim() || "安装计划任务失败" };
    }
    return taskStatus(name).then((status) => ({ ok: true, ...status }));
  });
}

function taskRemove(name) {
  const script = `
foreach ($name in @(${psQuote(name)}, ${psQuote(`${name}Unlock`)})) {
  $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
  if ($task) { Unregister-ScheduledTask -TaskName $name -Confirm:$false }
}
'ok'
`;
  return runPowerShell(script).then(({ code, err }) => {
    if (code !== 0) return { ok: false, error: err.trim() || "删除计划任务失败" };
    return { ok: true, installed: false };
  });
}

function taskRun(name) {
  const script = `Start-ScheduledTask -TaskName ${psQuote(name)}; 'ok'`;
  return runPowerShell(script).then(({ code, err }) => {
    if (code !== 0) return { ok: false, error: err.trim() || "没有跑起来" };
    return { ok: true };
  });
}

function setWallpaper(ps1, pngPath, style) {
  return new Promise((resolve) => {
    const child = spawn(
      "powershell.exe",
      ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", ps1, "-Path", pngPath, "-Style", style || "Fill"],
      { windowsHide: true },
    );
    let out = "";
    let err = "";
    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      resolve(result);
    };
    child.stdout.on("data", (chunk) => { out += chunk.toString("utf8"); });
    child.stderr.on("data", (chunk) => { err += chunk.toString("utf8"); });
    child.on("error", (error) => {
      remember(pngPath, `${new Date().toISOString()} fail spawn ${error.message}`);
      finish({ ok: false, error: error.message });
    });
    child.on("close", (code) => {
      if (code === 0) {
        remember(pngPath, `${new Date().toISOString()} ok`);
        finish({ ok: true });
        return;
      }
      const error = err.trim() || out.trim() || `设壁纸失败 ${code}`;
      remember(pngPath, `${new Date().toISOString()} fail ${code} ${error}`);
      finish({ ok: false, error });
    });
  });
}

module.exports = { taskStatus, taskInstall, taskRemove, taskRun, setWallpaper };
