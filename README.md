# Disposable Observability Stack (Ansible-Powered)

## 🎯 Project Intent
This project automates a production-grade observability stack (Grafana, Prometheus, Loki) on a single, low-cost VPS (specifically targeted for **IONOS VPS M** at ~$6-10/mo). 

The core philosophy is **Disposable Infrastructure**: The server itself is treated as a temporary resource. All configurations are version-controlled in this repository, and all persistent data (logs/metrics) should ideally be backed up or offloaded (e.g., Loki to S3) to allow for total server recreation with zero data loss.

## 🏗️ Architecture & Tooling
- **Platform:** IONOS VPS M (Ubuntu 22.04/24.04).
- **Configuration Management:** **Ansible** (Chosen over Terraform to maintain compatibility with fixed-price "package" VPS plans which lack robust API orchestration).
- **Deployment Strategy:** Docker Compose managed by Ansible.
- **Security:** UFW Firewall, Fail2Ban for SSH protection, and OS hardening via the `common` role.

## 📁 Project Structure
- `site.yml`: Main playbook orchestrating all roles.
- `inventory/`: Contains `production.yml` (host IPs) and `group_vars/` (configuration).
- `roles/common/`: Hardens the OS, configures UFW, and sets up Fail2Ban.
- `roles/docker/`: Installs the official Docker Engine and Compose plugin.
- `roles/observability/`: Templates the monitoring configs and launches the Docker stack.
- `roles/backup/`: Configures automated daily backups of all monitoring data.

## 🤖 AI Ingestion Context (For Copilot/Cursor)
When generating new tasks or roles, please adhere to these constraints:
1. **Role-Based Logic:** Always place logic in `roles/<role_name>/tasks/main.yml`.
2. **Variable Priority:** Use `inventory/group_vars/monitoring.yml` for user-defined variables.
3. **Secrets:** All sensitive data (passwords, S3 keys) must be prefixed with `vault_` and stored in an Ansible Vault-encrypted file.
4. **Idempotency:** Ensure all tasks are idempotent (only make changes if the current state differs from the desired state).
5. **Jinja2 Templates:** Use `.j2` templates for configuration files (Prometheus, Loki, Docker Compose) to allow for dynamic variable injection.

## 🚀 Deployment
1. **Install Ansible Collections:**
   ```bash
   ansible-galaxy collection install -r requirements.yml
   ```

2. Update `inventory/production.yml` with the target VPS IP.

3. **Option A:** Create a `.vault_pass` file with your vault password (recommended for automation):
   ```bash
   echo "your_vault_password" > .vault_pass
   chmod 600 .vault_pass
   ```
4. **Option B:** Use `--ask-vault-pass` flag to enter password interactively.

5. Execute:
   ```bash
   # Using .vault_pass file (configured in ansible.cfg)
   ansible-playbook site.yml
   
   # Or using interactive password prompt
   ansible-playbook site.yml --ask-vault-pass
   ```

## 💾 Backup & Restore
Automated backups run daily at 2 AM and are stored in `/opt/backups/` on the server. Backups are retained for 7 days.

To manually trigger a backup:
```bash
ssh root@your-server /usr/local/bin/backup-monitoring.sh
```

To restore from a backup, see `/opt/backups/RESTORE.md` on the server.
## 🛠️ Maintenance & Scaling
**Vertical Scaling:** If upgrading VPS size (e.g., M to L), update the RAM limits in `group_vars/monitoring.yml` and re-run the playbook.

**Disposability Test:** To test disposability:
1. Download latest backup from `/opt/backups/`
2. Delete the VPS and provision a fresh one
3. Run this playbook
4. Restore the backup
5. The stack should be fully functional in < 5 minutes

**Grafana Access:** After deployment, Grafana is accessible at `http://your-server-ip:3000` with Prometheus and Loki datasources pre-configured.


### **Why this helps AI tools:**
* **The "Why":** It explicitly explains that we chose **Ansible over Terraform** because of the IONOS budget constraints. This prevents the AI from suggesting Terraform fixes that won't work for your plan.
* **The "Where":** It defines exactly where the AI should look for variables (`group_vars`) and logic (`roles`).
* **The "Safety":** It enforces the use of **Ansible Vault**, ensuring the AI doesn't try to write plain-text passwords into your source code.

**Would you like me to generate a `.gitignore` file to ensure you don't accidentally commit your `.vault_pass` or local Python environments to GitHub?**