# Rclone Authorization for Colab Training

Use this when you want to let different Google accounts run Colab workers and upload checkpoints.

## Recommended setup: one shared Drive folder

This is the safest setup.

1. Pick one Google account as the owner.
2. Create this folder in that account's Google Drive:

   ```text
   My Drive/npdna_training
   ```

3. Share the `npdna_training` folder with every training account and give each account **Editor** access.
4. Authorize rclone only once on this machine, using the owner account.
5. Each Colab worker signs in with its own Google account, mounts Drive, and writes into the shared `npdna_training/workers/` folder.

The local scripts only need the owner rclone remote. The trainer accounts do not need your rclone token.

## Install rclone

Windows:

```powershell
winget install Rclone.Rclone
```

If `winget` is not available, download rclone from:

```text
https://rclone.org/downloads/
```

After installation, open a new PowerShell and check:

```powershell
rclone version
```

## Authorize the main Google Drive remote

Simplest Windows setup:

```powershell
powershell -ExecutionPolicy Bypass -File colab_distributed\setup_rclone_drive.ps1
```

The helper checks rclone, opens `rclone config` if `gdrive` is not ready,
creates `gdrive:npdna_training`, and deploys the training files.

Manual setup:

```powershell
rclone config
```

Choose:

```text
n) New remote
name> gdrive
Storage> drive
client_id> press Enter
client_secret> press Enter
scope> drive
root_folder_id> press Enter
service_account_file> press Enter
Edit advanced config? n
Use auto config? y
```

Your browser will open. Sign in with the owner Google account and allow access. Then test:

```powershell
rclone lsd gdrive:
rclone mkdir gdrive:npdna_training
```

Deploy files:

```powershell
python colab_distributed\monitor.py --setup
```

Sync completed workers:

```powershell
python colab_distributed\monitor.py --sync
```

## Multiple separate Drive accounts

Use this only if every account has its own Drive storage and you want separate remotes.

Automated loop for 10 accounts:

```powershell
powershell -ExecutionPolicy Bypass -File colab_distributed\setup_rclone_multi_accounts.ps1 -Count 10
```

Google will still require one browser sign-in and Allow screen per account.

Create one remote per Google account:

```powershell
rclone config
```

Use names like:

```text
gdrive_main
gdrive_acc2
gdrive_acc3
```

Run the scripts against a specific remote:

```powershell
$env:ATULYA_RCLONE_REMOTE="gdrive_acc2"
python colab_distributed\monitor.py --setup
python colab_distributed\monitor.py --sync
```

The scripts also support a different Drive folder name:

```powershell
$env:ATULYA_DRIVE_ROOT="npdna_training_account_2"
```

## Important security note

Do not send your `rclone.conf` file to other people. It contains OAuth tokens. To authorize another account, run `rclone config` again and let that person sign in in the browser, or use the shared-folder setup above.

To see where rclone stores tokens:

```powershell
rclone config file
```
