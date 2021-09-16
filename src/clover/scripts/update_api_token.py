import os

def main():
    if not os.path.isdir("locations"):
        raise Exception("You've got no locations yet!")

    token = input("Input your token.")

    for _, _, file in os.walk("locations"):
        ...

        update_your_token("generation_inputs.yaml")
