import qrcode
from PIL import Image

# Data to be encoded in the QR code
data = "https://docs.google.com/forms/d/e/1FAIpQLSeIRjakxp0aUCBK7X9VWL2HO1WWY6RwgYfpyfj0JpwDoX3u8A/viewform?usp=header"

# --- Create the QR Code ---
# High error correction is necessary for a logo
qr = qrcode.QRCode(
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=20,  # Controls the resolution
    border=4,
)
qr.add_data(data)
qr.make(fit=True)

# Create the QR code image, using RGB for color logo compatibility
qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

# --- Add the Logo ---
# Open the logo image
try:
    logo = Image.open("Logo.tif")
except FileNotFoundError:
    print("Error: 'logo.png' not found. Please ensure the logo file is in the same directory.")
    exit()

# --- Resize the Logo ---
# The logo should not cover more than 30% of the QR code
qr_width, qr_height = qr_img.size
logo_max_size = qr_height // 4

# Resize the logo to fit
logo.thumbnail((logo_max_size, logo_max_size))

# --- Position and Paste the Logo ---
# Calculate the position to center the logo
logo_pos = ((qr_width - logo.width) // 2, (qr_height - logo.height) // 2)

# Paste the logo onto the QR code image. [5]
qr_img.paste(logo, logo_pos)

# --- Save the Final Image ---
qr_img.save("1.png")

print("High-resolution QR code with logo saved as qr_with_logo.png")