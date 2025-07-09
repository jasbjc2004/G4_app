import os
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
        python_files=None,
):
    """
    Build a PyInstaller executable with robust file handling. (code from ChatGPT)
    """
    # Prepare PyInstaller command
    command = [
        sys.executable, '-m', 'PyInstaller',
        '--name', name,
        '--onefile',  # Create a single executable
        '--windowed',  # No console window
    ]

    if icon:
        command.extend(['--icon='+icon])

    if additional_files:
        for file_path in additional_files:
            directory_file = file_path[::-1].split('/', 1)[1][::-1]
            command.extend(['--add-data', f'{file_path}:{directory_file}'])

    if python_files:
        for file_path in python_files:
            print(str(file_path))
            command.extend(['--add-data', f'{file_path}:.'])

    if main_script:
        command.append(main_script)

    # Print the command for debugging
    print("Running PyInstaller command:")
    print(" ".join(command))

    try:
        # Run the PyInstaller command
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print("Build successful!")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Build failed!")
        print("Error output:", e.stderr)
        print("Command output:", e.stdout)


def main():
    python_files = []
    extra_files = []

    current_dir = os.path.dirname(os.path.abspath(__file__))
    for filename in os.listdir(current_dir):
        file_path = os.path.join(current_dir, filename)

        if os.path.isdir(file_path):
            continue

        elif filename.endswith('.py'):
            try:
                python_files.append(file_path.replace(current_dir, '.').replace('\\', '/'))
            except:
                print(f"Error: failed to get info from: {file_path}!")
                continue

    needed_files = os.path.join(current_dir, 'NEEDED', 'FILES')
    for filename in os.listdir(needed_files):
        file_path = os.path.join(needed_files, filename)

        if os.path.isdir(file_path):
            continue

        else:
            try:
                extra_files.append(file_path.replace(current_dir, '.').replace('\\', '/'))
            except:
                print(f"Error: failed to get info from: {file_path}!")
                continue

    needed_music = os.path.join(current_dir, 'NEEDED', 'MUSIC')
    for filename in os.listdir(needed_music):
        file_path = os.path.join(needed_music, filename)

        if os.path.isdir(file_path):
            continue

        else:
            try:
                extra_files.append(file_path.replace(current_dir, '.').replace('\\', '/'))
            except:
                print(f"Error: failed to get info from: {file_path}!")
                continue

    needed_pictures = os.path.join(current_dir, 'NEEDED', 'PICTURES')
    for filename in os.listdir(needed_pictures):
        file_path = os.path.join(needed_pictures, filename)

        if os.path.isdir(file_path):
            continue

        else:
            try:
                extra_files.append(file_path.replace(current_dir, '.').replace('\\', '/'))
            except:
                print(f"Error: failed to get info from: {file_path}!")
                continue

    # Determine main script (most likely main.py or the longest Python file)
    main_script = next(f for f in python_files if f.endswith('main.py')).replace('./','')

    # Detect icon file
    icon = [f for f in extra_files if f.endswith('.ico')][0]

    # Build the executable
    build_executable(
        main_script=main_script,
        name='final_test_software',
        icon=icon,
        additional_files=extra_files,
        python_files=None
    )


if __name__ == '__main__':
    import glob

    main()