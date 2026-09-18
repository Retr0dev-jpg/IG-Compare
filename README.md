# IG Compare

Compare Instagram followers and following from an official data export. No login, no scraping, no extra dependencies.

It shows who you follow that does not follow you back, and who follows you that you do not follow. Click a username to open the profile.

## 1. Download your Instagram data

Go to your Instagram account settings through the Account Center:

1. Visit https://accountscenter.instagram.com/info_and_permissions/?theme=dark
2. Select **Download your information**
3. Request a download of your data (HTML or JSON)
4. Wait for Instagram to prepare your data (you will receive an email)
5. Once you receive the email, download your data as a ZIP file

Do not unzip it. The app reads the ZIP as it is.

## 2. Run the app (using code)

```
python main.py
```

1. Click **Load export…**
2. Select the ZIP you downloaded (or the HTML/JSON files, if you already extracted them)
3. The lists fill in on their own

If the ZIP is in the same folder as the app, it loads at startup.

Click a username to open the Instagram profile. **Export .txt** saves the current list.

Windows, Linux, and macOS builds are published to **Releases** (tag `latest` on each push to main, or a version tag like `v1.0.0`).
