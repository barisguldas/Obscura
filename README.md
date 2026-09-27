# Obscura

Obscura is a secure, end-to-end encrypted desktop chat application that combines modern cryptography with digital steganography. It is designed to provide secure, untraceable, and aesthetically modern communication.

## Architecture and Security

Obscura employs a hybrid encryption model alongside steganographic data concealment principles:

* **End-to-End Encryption (E2EE):** Utilizes 1024-bit RSA for secure public key exchange and AES (via Fernet) for symmetric message encryption. The server acts strictly as a routing node and has no capacity to decrypt communications.
* **Steganographic Concept:** Encrypted payloads are structurally associated with user avatars acting as carrier images, providing an additional layer of data obfuscation.
* **Store and Forward Mechanism:** Messages directed to offline peers are stored as encrypted blobs on the server and are reliably delivered upon their next authentication.
* **Local Key Management:** Asymmetric private keys are generated entirely client-side and never leave the host machine.

## Features

* **Asynchronous Multi-Client Server:** Thread-safe socket architecture handling multiple concurrent TCP connections.
* **Dynamic Group Chats:** Secure multi-party messaging with administrative access controls and invitation systems.
* **Modern Graphical Interface:** Developed with CustomTkinter, featuring a responsive, split-pane layout with an integrated dark theme.
* **Advanced Image Processing:** Integrates Super Sample Anti-Aliasing (SSAA) and Lanczos resampling for high-fidelity circular UI rendering.
* **Persistent Storage:** Local JSON-based caching for encrypted chat histories, network configurations, and session management.

## Installation and Usage

### Prerequisites
* Python 3.8 or higher
* Required dependencies: `customtkinter`, `cryptography`, `Pillow`

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/barisguldas/Obscura.git
   cd Obscura
   ```

2. Install the required Python packages:
   ```bash
   pip install customtkinter cryptography Pillow
   ```

3. Start the server routing node:
   ```bash
   python server/server.py
   ```

4. Launch the graphical client:
   ```bash
   python client/client_gui.py
   ```

## Disclaimer
This project is developed for educational and research purposes in the fields of cybersecurity, applied cryptography, and network programming.
