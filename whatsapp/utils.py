import requests
import os

def download_and_save_image(image_id, token, folder='order_images'):
    """Download image from Meta and save permanently to server"""
    try:
        if not image_id or image_id in ['received', 'N/A', '']:
            return ''

        # Step 1: Get media URL
        meta_url = f"https://graph.facebook.com/v18.0/{image_id}"
        r = requests.get(
            meta_url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "curl/7.68.0"
            },
            timeout=15
        )
        if r.status_code != 200:
            print(f"Meta API error: {r.status_code} - {r.text}")
            return ''

        media_url = r.json().get('url', '')
        if not media_url:
            print("No URL in Meta response")
            return ''

        # Step 2: Download image binary
        img_r = requests.get(
            media_url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "curl/7.68.0"
            },
            timeout=30
        )

        if img_r.status_code != 200:
            print(f"Image download error: {img_r.status_code}")
            return ''

        # Step 3: Save to server
        media_dir = f"/home/macfedo_bot/media/{folder}"
        os.makedirs(media_dir, exist_ok=True)
        filename = f"{image_id}.jpg"
        filepath = os.path.join(media_dir, filename)

        with open(filepath, 'wb') as f:
            f.write(img_r.content)

        local_url = f"https://api.macfedowears.com/media/{folder}/{filename}"
        print(f"✅ Image saved: {local_url}")
        return local_url

    except Exception as e:
        print(f"Image error: {e}")
        return ''
