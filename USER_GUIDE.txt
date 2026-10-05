====================================================
 File Control - User guide
====================================================

WHAT TO COPY
------------
Copy this entire folder to the user's machine:
  - FileControl.exe   (the program)
  - config.json       (the settings, editable)

Keep both files in the same folder.


STARTING THE PROGRAM
--------------------
Simply double-click "FileControl.exe".
No Python or Visual Studio Code installation is required.

Note: on the first launch, Windows may show a SmartScreen warning
("Windows protected your PC"). Click "More info" then "Run anyway".


HOW TO USE
----------
1. Choose a folder or a .zip file to check.
2. Click "Start check".
3. The program lists the rejected files (unsupported format
   or file too large).
4. A question appears: create the .zip archives? Answer Yes or No.
5. If Yes, the archives are created in a new "<name>_NEW" folder
   located next to the original folder/zip.


SETTINGS (config.json)
----------------------
You can open config.json with Notepad to adjust:
  - max_file_size_mb   : maximum size of a file (MB)
  - max_zip_size_mb    : maximum size of a produced archive (MB)
  - allowed_extensions : accepted formats
  - convert_unsupported: convert unsupported formats


FORMAT CONVERSION (optional)
----------------------------
Converting OpenOffice formats (.odt, .ods, .odp...) to Office
formats (.docx, .xlsx, .pptx) requires LibreOffice installed on
the machine. Without LibreOffice, those files are simply rejected.
Download: https://www.libreoffice.org/
