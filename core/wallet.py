import os
from dataclasses import dataclass
from solders.keypair import Keypair


class WalletManager:

    @classmethod
    def load_keypair(cls, address: str, wallet_directory: str = "./") -> Keypair:
        keypair_file = os.path.join(
            wallet_directory,
            f"{address}.key"
        )
        with open(keypair_file, 'rb') as f:
            data = f.read()
        return Keypair.from_bytes(data)

    @classmethod
    def save_keypair(cls, keypair: Keypair, wallet_directory: str = "./") -> str:
        keypair_file = os.path.join(
            wallet_directory,
            f"{keypair.pubkey()}.key"
        )
        keypair_bytes = keypair.to_bytes()
        with open(keypair_file, 'wb') as f:
            f.write(keypair_bytes)

        return keypair_file

    @classmethod
    def generate_keypair(save_to_file: bool = True) -> tuple:
        keypair = Keypair()
        keypair_file = WalletManager.save_keypair(keypair)
        return (keypair_file, keypair)
