from core.wallet import WalletManager


def main():
    file, keypair = WalletManager.generate_keypair()
    print(f"Newly generated keypair saved to {file}")


if __name__ == "__main__":
    main()
