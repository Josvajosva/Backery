# Change Log — website_pincode_delivery_check

---

## 2026-06-15

### 1. Extracted inline CSS to separate static file
- **New file**: `static/src/css/landing_page.css`
- **Reason**: CSS was inline inside `views/website_landing_views.xml` inside a `<style>` block — not Odoo standard practice.
- **CSS moved**: `.order-option-btn:hover`, `.order-option-btn:active`, `.form-select:focus`, `.form-control:focus`

---

### 2. Extracted inline JavaScript to separate static file
- **New file**: `static/src/js/landing_page.js`
- **Reason**: JS was inline inside `views/website_landing_views.xml` inside a `<script>` block — not Odoo standard practice.
- **Functions moved**: `selectOption()`, `confirmPickup()`, `confirmDelivery()`, `submitSelection()`
- **Key change**: All 4 functions are attached to `window` (e.g. `window.selectOption = function(...)`) so they remain globally accessible after Odoo bundles the file. The `onclick="..."` attributes in the HTML continue to work.

---

### 3. Removed inline `<style>` and `<script>` from landing page XML
- **File**: `views/website_landing_views.xml`
- **Removed**: The entire `<style>` block and `<script>` block at the bottom of the template
- **Result**: The template now only contains HTML structure. CSS and JS are loaded via the asset bundle.

---

### 4. Added `assets` key to manifest
- **File**: `__manifest__.py`
- **Change**:
  ```python
  'assets': {
      'web.assets_frontend': [
          'website_pincode_delivery_check/static/src/css/landing_page.css',
          'website_pincode_delivery_check/static/src/js/landing_page.js',
      ],
  },
  ```
- **Reason**: Registers the new static CSS and JS files into Odoo's frontend asset bundle (`web.assets_frontend`) — the standard Odoo 18 way to load website static files.

---

### 5. Added login redirect before Shop and Product pages
- **File**: `controllers/main.py`
- **Methods**: `shop()` and `product()` in `WebsitePincodeSale`
- **Change added**:
  ```python
  if request.env.user._is_public():
      return request.redirect('/web/login?redirect=/landing')
  ```
- **Flow**: Shop click → Login page → after login → Landing page (delivery selection) → Shop
- **Reason**: Guest/public users must log in before selecting a delivery option and accessing the shop.

---

### 6. Added `WebsiteSignup` controller — portal user login/signup redirect
- **File**: `controllers/main.py` — new `WebsiteSignup` class appended at bottom
- **File**: `__manifest__.py` — added `auth_signup` to `depends` list
- **Problem**: After login or signup, portal users were being sent to `/odoo` (backend), which caused an "ir.ui.menu" access error because portal users have no backend menu access.
- **Fix**: Three-layer override using `WebsiteSignup(AuthSignupHome)`:
  1. `/web/signup` POST — after successful signup, portal user → `/landing`
  2. `/web/login` POST — after successful login, portal user → `/landing`
  3. `/web/login_successful` — fallback catchall, portal user → `/landing`
- **Result**: Portal users always land on the delivery selection page after login/signup, never on the backend.