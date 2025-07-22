import os
import shutil
import subprocess
import sys

"""
code to load all the important files and make an .exe from the main-file to a working project
.exe can be found in the dist-directory
"""


def build_executable(
        main_script=None,
        name='app',
        icon=None,
        additional_files=None,
):
    """
    Build a PyInstaller executable with robust file handling. (code from ChatGPT)
    """
    # Prepare PyInstaller command
    command = [
        sys.executable, '-m', 'PyInstaller',
        '--name', name,
        '--onedir',
        '--windowed',  # No console window
        '--collect-all=scipy'
    ]

    if icon:
        command.extend(['--icon='+icon])

    if additional_files:
        for file_path in additional_files:
            directory_file = '/'.join(file_path.split('/')[:-1])
            command.extend(['--add-data', f'{file_path}:{directory_file}'])

    if main_script:
        command.append(main_script)

    # Print the command for debugging
    print("Running PyInstaller command:")
    print(" ".join(command))

    input("Command ready, press enter to continue")

    try:
        # Run the PyInstaller command
        result = subprocess.run(command, check=True, text=True)
        print("Build successful!")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Build failed!")
        print("Error output:", e.stderr)
        print("Command output:", e.stdout)


def main():
    app_name = 'final_test_software'
    input("Are you sure you want to delete the previous app?")

    folders_to_remove = ["dist", "build", "__pycache__"]
    for folder in folders_to_remove:
        if os.path.exists(folder):
            shutil.rmtree(folder)

    spec_file = app_name+'.spec'
    if os.path.exists(spec_file):
        os.remove(spec_file)


    input("All files deleted, press enter to continue")

    main_script = "main.py"
    if not os.path.exists(main_script):
        print(f"Error: no main-file found")
        return

    extra_files = []
    current_dir = os.path.dirname(os.path.abspath(__file__))

    for filename in os.listdir(current_dir):
        file_path = os.path.join(current_dir, filename)

        if os.path.isfile(file_path) and filename.endswith('.keras'):
            extra_files.append(file_path.replace(current_dir, '.').replace('\\', '/'))

    needed_files = os.path.join(current_dir, 'NEEDED', 'FILES')
    if os.path.exists(needed_files):
        for filename in os.listdir(needed_files):
            file_path = os.path.join(needed_files, filename)
            if not os.path.isdir(file_path):
                try:
                    extra_files.append(file_path.replace(current_dir, '.').replace('\\', '/'))
                except:
                    print(f"Error: failed to get info from: {file_path}!")
                    continue

    needed_music = os.path.join(current_dir, 'NEEDED', 'MUSIC')
    if os.path.exists(needed_music):
        for filename in os.listdir(needed_music):
            file_path = os.path.join(needed_music, filename)
            if not os.path.isdir(file_path):
                try:
                    extra_files.append(file_path.replace(current_dir, '.').replace('\\', '/'))
                except:
                    print(f"Error: failed to get info from: {file_path}!")
                    continue

    needed_pictures = os.path.join(current_dir, 'NEEDED', 'PICTURES')
    if os.path.exists(needed_pictures):
        for filename in os.listdir(needed_pictures):
            file_path = os.path.join(needed_pictures, filename)
            if not os.path.isdir(file_path):
                try:
                    extra_files.append(file_path.replace(current_dir, '.').replace('\\', '/'))
                except:
                    print(f"Error: failed to get info from: {file_path}!")
                    continue

    # Detect icon file
    icon = [f for f in extra_files if f.endswith('.ico')][0]

    # Build the executable
    build_executable(
        main_script=main_script,
        name=app_name,
        icon=icon,
        additional_files=extra_files,
    )


if __name__ == '__main__':
    import glob

    main()
