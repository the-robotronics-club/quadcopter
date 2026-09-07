Drop flight photos here (*.jpg, *.jpeg, *.png, *.webp, *.avif).
After `git push`, the live site auto-discovers them via the GitHub Contents API:
GET /repos/the-robotronics-club/quadcopter/contents/website/assets/gallery
Then rebuild: python3 build.py
