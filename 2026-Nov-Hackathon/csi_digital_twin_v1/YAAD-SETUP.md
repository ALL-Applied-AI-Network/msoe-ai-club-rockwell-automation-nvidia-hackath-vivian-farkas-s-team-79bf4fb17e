# YAAD setup for teammates

This guide covers getting a teammate's Copilot session and computer connected to the team's YAAD environment, and checking that the digital-twin project is available there. It does not claim that rendering this project on YAAD has been validated.

## 1. Get YAAD account access

1. Make sure you have been added to the CSI YAAD team and can sign in to the YAAD website.
2. Connect to the CSI network or VPN if required.
3. In your Copilot environment, check that the YAAD MCP server is available. This project's setup used the user-level file:

   ```text
   C:\Users\<your-Windows-user>\.copilot\mcp-config.json
   ```

   Its server entry points to `https://www.yaadops.com/api/mcp`, uses HTTP transport, and authenticates with an authorization header. Keep the actual authorization value private. Do not copy another person's token or commit it to this project. Your organization may provision this file for you.
4. In Copilot, use YAAD's account/session tool to confirm that the YAAD tools respond and obtain **your own** SSH username and host. The username is account-specific. In the commands below, replace `YOUR_YAAD_USER` and `YOUR_YAAD_HOST` with those values.

If the YAAD tools are unavailable, ask your administrator to configure or enable the MCP server. Do not paste an authorization token into chat or a project file.

## 2. Register and test your SSH key

YAAD SSH access uses the public key registered to your YAAD account. If you already have a key, use its matching `.pub` file. Otherwise, create an Ed25519 key in PowerShell:

```powershell
ssh-keygen -t ed25519 -C "your-email@example.com"
```

Register the **public** key (the file ending in `.pub`) with your YAAD account using the YAAD website's SSH-key settings. Never upload or share the private key file, which has no `.pub` suffix.

Test direct SSH access using the username and host returned for your account:

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" `
  -o IdentitiesOnly=yes `
  YOUR_YAAD_USER@YOUR_YAAD_HOST
```

Enter your key's passphrase only into the local SSH prompt. After login, confirm that `/workspace` is present:

```bash
pwd
ls -la /workspace
```

### Optional: load your key into the Windows SSH agent

An SSH agent is convenient but not required if direct SSH with `-i` works. If you want to use the agent, open PowerShell **as Administrator** and run:

```powershell
Set-Service ssh-agent -StartupType Manual
Start-Service ssh-agent
```

Then, in your regular PowerShell terminal:

```powershell
ssh-add "$env:USERPROFILE\.ssh\id_ed25519"
ssh-add -l
```

If Windows cannot start the agent, use the direct `ssh -i` command above instead. Do not send your passphrase or private key to anyone.

## 3. Check the shared project workspace

Use SSH to inspect the team workspace before uploading anything:

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" `
  -o IdentitiesOnly=yes `
  YOUR_YAAD_USER@YOUR_YAAD_HOST `
  'find /workspace -maxdepth 3 -type f -print'
```

The project may already be present in a directory such as `/workspace/csi_digital_twin_v1`. If it is, verify that it contains the expected project files, including:

```text
cameras/FillCam.json
stations/fill_station/fill_station.usda
stations/fill_station/geometry/fill_station.usdc
tools/render_example.py
```

Keep the folder hierarchy intact: USD files refer to other assets using relative paths.

If the project is not present, first create its destination from PowerShell:

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" `
  -o IdentitiesOnly=yes `
  YOUR_YAAD_USER@YOUR_YAAD_HOST `
  'mkdir -p /workspace/csi_digital_twin_v1'
```

Then, from the project directory on your Windows computer, copy the files:

```powershell
scp -i "$env:USERPROFILE\.ssh\id_ed25519" -r `
  .\cameras .\stations .\tools .\README.md .\csi_line.usda `
  YOUR_YAAD_USER@YOUR_YAAD_HOST:/workspace/csi_digital_twin_v1/
```

Then use SSH to verify the copied files at `/workspace/csi_digital_twin_v1`. The full project includes large USD assets; check available storage and whether the shared copy already exists before transferring it again.

## 4. Isaac Sim version and YAAD jobs

- The project README says it was tested with **Isaac Sim 6.0**. Use the YAAD image `nvcr.io/nvidia/isaac-sim:6.0.0` for work that needs this project's Isaac Sim setup.
- YAAD's generic job-sizing suggestion may name a different Isaac Sim image. Treat that as a generic suggestion; the project-tested version takes precedence unless the team deliberately validates another version.
- Isaac Sim jobs need these environment variables:

  ```text
  ACCEPT_EULA=Y
  PRIVACY_CONSENT=Y
  ```

- YAAD jobs take an input directory from the shared workspace and expose it inside the container as `/job/in`. Write job outputs under `/job/out` so YAAD can preserve them as job results.
- Use the YAAD MCP to submit and check jobs. Wait for a terminal status and inspect the job logs and outputs; do not assume that a submitted or running job has succeeded.
- This guide records setup and access only. It does not assert that the project's render script has successfully produced an image on YAAD.
