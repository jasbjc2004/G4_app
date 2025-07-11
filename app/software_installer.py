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
        #'--collect - all'
    ]

    if icon:
        command.extend(['--icon='+icon])

    if additional_files:
        for file_path, dest_path in additional_files:
            command.extend(['--add-data', f'{file_path}:{dest_path}'])

    if main_script:
        command.append(main_script)

    # Print the command for debugging
    print("Running PyInstaller command:")
    print(" ".join(command))

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

    app_folder = os.path.join("dist", app_name)
    if os.path.exists(app_folder):
        shutil.rmtree(app_folder)

    if os.path.exists("build"):
        shutil.rmtree("build")

    spec_file = app_name+'.spec'
    if os.path.exists(spec_file):
        os.remove(spec_file)

    input("All files deleted, press enter to continue")

    extra_files = []
    current_dir = os.path.dirname(os.path.abspath(__file__))

    for filename in os.listdir(current_dir):
        file_path = os.path.join(current_dir, filename)

        if os.path.isfile(file_path) and filename.endswith('.keras'):
            extra_files.append((file_path, '.'))

    needed_files = os.path.join(current_dir, 'NEEDED', 'FILES')
    if os.path.exists(needed_files):
        for filename in os.listdir(needed_files):
            file_path = os.path.join(needed_files, filename)
            if os.path.isfile(file_path):
                extra_files.append((current_dir, '.'))

    needed_music = os.path.join(current_dir, 'NEEDED', 'MUSIC')
    if os.path.exists(needed_music):
        for filename in os.listdir(needed_files):
            file_path = os.path.join(needed_files, filename)
            if os.path.isfile(file_path):
                extra_files.append((current_dir, '.'))

    needed_pictures = os.path.join(current_dir, 'NEEDED', 'PICTURES')
    if os.path.exists(needed_pictures):
        for filename in os.listdir(needed_files):
            file_path = os.path.join(needed_files, filename)
            if os.path.isfile(file_path):
                extra_files.append((current_dir, '.'))

    main_script = None
    for filename in os.listdir(current_dir):
        if filename == "main.py":
            main_script = os.path.join(current_dir, filename)
            break

    if not main_script:
        print("Error: main.py not found!")
        return

    # Detect icon file
    icon = None
    for file_path, dest_path in extra_files:
        if file_path.endswith('.ico'):
            icon = file_path
            break

    # Build the executable
    build_executable(
        main_script=main_script,
        name=app_name,
        icon=icon,
        additional_files=extra_files,
    )


if __name__ == '__main__':
    main()
