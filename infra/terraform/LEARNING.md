# Learning Terraform on the garden app

A hands-on walkthrough. You run every command, and each step says what you
should see and why. Phase 1 brings the Google Cloud resources the app already
uses under Terraform. Phases 2–4 (Neon, Sentry, GitHub secrets) come later.

Render is **not** managed here. It's already infrastructure-as-code via
`render.yaml` (a Render Blueprint). Two tools managing the same service would
overwrite each other's changes.

## The mental model (read once)

| Concept | One-line version |
|---|---|
| **Configuration** | The `.tf` files: the infrastructure you *want*. |
| **Provider** | A plugin that talks to one API (`hashicorp/google`). Downloaded by `terraform init`. |
| **Resource** | One real object, e.g. `resource "google_storage_bucket" "static"`. Its address is `google_storage_bucket.static`. |
| **State** | Terraform's record of which real object each resource address maps to, plus its last-known attributes. |
| **Plan** | Compares configuration vs. state vs. reality, then lists what it *would* do. Changes nothing. |
| **Apply** | Carries out a plan (after you type `yes`). |
| **Import** | Adopts an object that already exists into state, instead of creating a new one. |
| **Drift** | Someone changed the real object outside Terraform. The next plan shows it. |

Plan symbols: `+` create, `-` destroy, `~` update in place, `-/+` destroy and
recreate (dangerous for anything holding data).

The golden rule while importing existing infrastructure: **if the plan wants to
change an imported resource, fix the code, not the cloud.** The goal is a plan
that says `No changes`, because that proves the code describes reality exactly.

## Prerequisites (once)

```powershell
winget install Hashicorp.Terraform      # then open a NEW terminal
terraform -version                      # expect v1.16.x or newer
gcloud auth application-default login   # Terraform will act as YOU, not the app's robot account
```

Every command below runs from `infra/terraform/`:

```powershell
cd infra\terraform
```

## Phase 1: Google Cloud (image bucket, service account, IAM, state bucket)

What's in the files:

- `versions.tf`: the Terraform and provider versions, plus the remote-state backend (commented out for now).
- `providers.tf`: the Google provider, using your gcloud login.
- `variables.tf`: the project id and region.
- `gcs.tf`: the **three existing** resources, each with an `import {}` block.
- `state.tf`: the **one new** resource, a private versioned bucket for state.
- `outputs.tf`: values printed after apply.

### 1a. Init, format, validate

```powershell
terraform init
terraform fmt
terraform validate
```

- `init` downloads the Google provider into `.terraform/` (gitignored). It also writes `.terraform.lock.hcl`, which you should commit.
- `fmt` rewrites files into canonical style. No output means they were already tidy.
- `validate` should print `Success! The configuration is valid.` It checks syntax and types but doesn't contact Google.

### 1b. Plan, then reconcile any differences

```powershell
terraform plan
```

What you want to see at the bottom:

```
Plan: 3 to import, 1 to add, 0 to change, 0 to destroy.
```

- **3 to import**: the image bucket, the service account, and the IAM grant.
- **1 to add**: `google_storage_bucket.tfstate`.

If it says `N to change` instead, scroll up to the `~` lines. Each one is an
attribute where the code and the real bucket disagree. For example:

```
~ resource "google_storage_bucket" "static" {
    ~ some_setting = "real-value" -> "code-value"
```

To fix it, edit the value in `gcs.tf` to match the left-hand (real) side, then
run `terraform plan` again. Repeat until the imported resources show no `~`.
Do **not** apply a plan that changes `google_storage_bucket.static`. That's the
live image store.

**What actually happened on the first run.** The plan said `1 to change` and
showed `- encryption { ... restriction_mode = "FullyRestricted" -> null }`.
Google had put encryption-enforcement settings on the bucket without being
asked. Because the code didn't mention them, Terraform planned to remove them.
Applying would have changed a security setting on the live image store without
anyone deciding to. The fix was an `encryption { ... }` block in `gcs.tf` that
copies the real values. Lesson: an omitted block doesn't mean "don't care". It
means "should not exist".

There's a helper when a resource has many unknown settings. Temporarily delete
its `resource` block (keep its `import` block) and run:

```powershell
terraform plan -generate-config-out=generated.tf
```

Terraform writes HCL describing the real object. Copy what you need back into
`gcs.tf`, then delete `generated.tf`.

### 1c. Apply

```powershell
terraform apply
```

It shows the same plan and asks `Enter a value:`. Type `yes`. Expect:

```
Apply complete! Resources: 3 imported, 1 added, 0 changed, 0 destroyed.
Outputs:
server_service_account = "garden-app-server@innate-conquest-491313-k3.iam.gserviceaccount.com"
static_bucket = "garden-app-static"
tfstate_bucket = "innate-conquest-491313-k3-tfstate"
```

You now have a local `terraform.tfstate`. Open it and look. It's plain JSON,
which is exactly why it must never be committed. It's gitignored.

### 1d. Move state into the bucket (remote backend)

This is a chicken-and-egg problem. The state bucket had to exist before
Terraform could store state in it, which is why its backend block was
commented out.

1. In `versions.tf`, uncomment the `backend "gcs" { ... }` block.
2. Run:

   ```powershell
   terraform init -migrate-state
   ```

   When it asks `Do you want to copy existing state to the new backend?`, answer `yes`.
3. Check the state landed in the bucket:

   ```powershell
   gcloud storage ls gs://innate-conquest-491313-k3-tfstate/garden-app/
   # expect: .../garden-app/default.tfstate
   ```

4. Delete the now-stale local copies, `terraform.tfstate` and `terraform.tfstate.backup`.

Every future `plan` and `apply` reads and writes state in the bucket. The
backend also takes a **lock** while a command runs, so two applies can't
corrupt state.

### 1e. Prove it: "No changes"

```powershell
terraform plan
# No changes. Your infrastructure matches the configuration.
terraform state list
# google_service_account.server
# google_storage_bucket.static
# google_storage_bucket.tfstate
# google_storage_bucket_iam_member.server_object_admin
```

Now delete the three `import { ... }` blocks from `gcs.tf`. They've done their
job, since the objects are in state. Run `terraform plan` again, and it should
still say `No changes`.

Finally, check the app didn't notice anything. Open any plant image on
https://garden-app-wa0b.onrender.com, or run:

```powershell
gcloud storage buckets get-iam-policy gs://garden-app-static   # garden-app-server still has objectAdmin
```

### Bonus: see drift detection

1. In the Cloud Console, go to Storage → `garden-app-static` → Configuration and add a label, e.g. `owner = me`.
2. Run `terraform plan`. It proposes removing the label (`~ labels`), because the code doesn't have one.
3. You now have two choices:
   - Add `labels = { owner = "me" }` to `gcs.tf`, which accepts the change into code.
   - Run `terraform apply`, which reverts the console change.

   Either way, the next plan says `No changes`. This is the day-to-day value of
   Terraform: the code is the source of truth, and any drift away from it gets
   flagged.

## Phase 2: Neon (the database)

Phase 1 is done. It was applied, state lives in the bucket, and the plan was
clean on 2026-09-30.

This phase imports **one** resource, `neon_project.garden` in `neon.tf`. Behind
it sit five Neon objects: the project, root branch, compute, `neondb` database
and `neondb_owner` role. The mechanics are the same as Phase 1, but the stakes
are higher, because this resource *is* the app's data.

New concepts:

- **Multiple providers.** `versions.tf` now asks for `kislerdm/neon` as well as `google`, and `init` downloads both.
- **Replacement (`-/+`).** Some arguments can't change in place. If one of them differs, Terraform plans to delete the database and make a new one.
  - `prevent_destroy` turns that plan into an error.
  - Still, **read every Phase 2 plan line by line**, and never apply one containing `-/+` or `destroy`.
- **Secrets in state.** `connection_uri` is marked `sensitive`, so plans print `<sensitive>`. That is display redaction only. `terraform output <name>` prints the real value, and the state file stores the password in plain text.

### 2a. API key, then init

1. Neon console → your avatar → **Account settings → API keys → Create new API key**. Copy it (it's shown once).
2. Put it in the **current PowerShell session only**. Don't save it to a file:

   ```powershell
   $env:NEON_API_KEY = "napi_..."
   ```

   You'll have to set it again in each new terminal. That's the price of never storing it on disk. (Phase 4 has a better answer.)
3. Download the new provider. Plain `init` is enough: the backend didn't change, only the providers did.

   ```powershell
   terraform init
   ```

   You should see `Installing kislerdm/neon v0.18.x`. The lock file gains a `neon` entry, so commit it.

### 2b. Plan and reconcile

```powershell
terraform plan
```

Target: `Plan: 1 to import, 0 to add, 0 to change, 0 to destroy.`

This is the same loop as step 1b. Any `~` line inside `neon_project.garden` is a
value in `neon.tf` that doesn't match Neon. Copy the live (left-hand) value into
the code and plan again. Likely candidates are `maintenance_window`, `branch`,
`quota` and `default_branch_protected`.

**Stop and paste the plan to Claude** if you see any of these:

- `-/+`, `must be replaced`, or `destroy`
- an error mentioning `prevent_destroy` (that means a replacement was attempted and blocked)

### 2c. Apply, then confirm

```powershell
terraform apply        # should say: 1 imported, 0 added, 0 changed, 0 destroyed
terraform plan         # No changes.
terraform output                            # the listing: neon_connection_uri = <sensitive>
terraform output neon_database_host         # not secret
```

**Careful.** `sensitive` only hides a value in plan/apply output and in the
all-outputs listing above. Asking for one output by name does not hide it:
`terraform output neon_connection_uri` and `terraform output -raw ...` both
print the real password.

This actually happened on the first run. The docs wrongly said the by-name
command would print `<sensitive>`, the password got pasted into a chat, and it
had to be rotated (step 2d). Treat any command that names a sensitive output as
"shows the secret".

Then delete the `import { ... }` block from `neon.tf` and run `terraform plan`
again. It should still say `No changes`.

### 2d. Rotating the password (and why state goes stale)

Rotate whenever the password has been exposed. It was on 2026-09-30, pasted
into a chat. The password lives in four places, and Terraform owns none of
them yet. Phase 4 fixes that.

1. **Neon:** open the console, then Branches → `production` → Roles → `neondb_owner` → **Reset password**. Copy the new password.
2. **Render:** Dashboard → garden-app → Environment → `DATABASE_URL`. Swap in the new password and keep the `postgresql+psycopg://` prefix. Saving triggers a redeploy.

   The live app can't reach the database between steps 1 and 2, so do them back to back.
3. **GitHub Actions:** the `DATABASE_URL` secret, used by `train_model.yaml`:

   ```powershell
   gh secret set DATABASE_URL     # paste the new URL at the prompt; it isn't echoed
   ```

4. **Local:** `DATABASE_URL` in the repo's `.env`.
5. **Terraform state:**

   ```powershell
   terraform plan -refresh-only
   ```

   Terraform read the old password during the import and saved it in state. The reset happened outside Terraform, so state is stale: that's drift. This command reports that `database_password` and the connection URIs changed, without proposing any change to Neon.

   ```powershell
   terraform apply -refresh-only
   ```

   Type `yes`. This rewrites state only, and touches nothing in Neon.

Where this is heading: in Phase 4, Terraform writes the GitHub secret from
`neon_project.garden.connection_uri`. After that, step 3 becomes part of
`terraform apply` instead of a manual step.

## Coming next

- **Phase 3, Sentry.** Import the `garden-app-backend` project and add an alert rule as code.
- **Phase 4, GitHub Actions secrets.** Feed Neon's connection string straight into the `DATABASE_URL` secret, so one provider's output becomes another's input.

## Cheat sheet

```powershell
terraform plan                          # what would change?
terraform apply                         # do it (asks first)
terraform state list                    # what does Terraform manage?
terraform state show <address>          # everything it knows about one resource
terraform output                        # print outputs again
terraform plan -refresh-only            # show drift only, without proposing code changes
terraform fmt; terraform validate       # tidy + sanity-check the files
```
