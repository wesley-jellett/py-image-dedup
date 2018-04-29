import os
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from py_image_dedup.library.DeduplicationResult import DeduplicationResult
from py_image_dedup.persistence.ImageSignatureStore import ImageSignatureStore


class ImageMatchDeduplicator:
    EXECUTOR = ThreadPoolExecutor()

    def __init__(self, directories: [str], file_extension_filter: [str] = None, max_dist: float = 0.03,
                 threads: int = 1):
        self._directories: [str] = directories
        self._file_extension_filter: [str] = file_extension_filter
        self._persistence: ImageSignatureStore = ImageSignatureStore(max_dist=max_dist)
        self._threads: int = threads

        self._files_count: int = 0

        self._progress_bar: tqdm = None

        self._deduplication_result: DeduplicationResult = None

    def analyze(self, recursive: bool) -> {str, str}:
        """
        Analyzes all files, generates identifiers (if necessary) and stores them
        for later access
        :return: file_path -> identifier
        """

        print("Analyzing files...")

        for directory in self._directories:
            with ThreadPoolExecutor(self._threads) as self.EXECUTOR:
                print("Counting files in '%s' ..." % directory)
                file_count = self._update_files_count(directory, recursive)

                self._create_progressbar(file_count)
                self._walk_directory(root_directory=directory,
                                     recursive=recursive,
                                     command=lambda file_path: self._analyze_file(file_path))

    def deduplicate(self, recursive: bool, dry_run: bool = False) -> DeduplicationResult:
        """
        Removes duplicates

        :param recursive:
        :param dry_run:
        :return:
        """

        self._deduplication_result = DeduplicationResult()

        self.analyze(recursive)

        for directory in self._directories:
            with ThreadPoolExecutor(self._threads) as self.EXECUTOR:
                print("Counting files in '%s' to process..." % directory)
                file_count = self._update_files_count(directory, recursive)

                print("Processing '%s' ..." % directory)
                self._create_progressbar(file_count)
                self._walk_directory(root_directory=directory,
                                     recursive=recursive,
                                     command=lambda file_path: self._remove_duplicates(file_path, dry_run=dry_run))

        # remove empty folders
        for directory in self._directories:
            self._remove_empty_folders(directory, remove_root=True, dry_run=dry_run)

        return self._deduplication_result

    def _walk_directory(self, root_directory: str, recursive: bool, command):
        """
        Walks through the files of the given directory

        :param root_directory: the directory to start with
        :param recursive: also walk through subfolders recursively
        :param command: the method to execute for every file found
        :return: file_path -> identifier
        """

        # to avoid ascii char problems
        root_directory = str(root_directory)
        for (root, dirs, files) in os.walk(root_directory):
            # root is the place you're listing
            # dirs is a list of directories directly under root
            # files is a list of files directly under root

            for file in files:
                file_path = os.path.abspath(os.path.join(root, file))

                # skip file with unwanted file extension
                if not self._file_extension_matches_filter(file):
                    continue

                # skip if not existent (probably already deleted)
                if not os.path.exists(file_path):
                    continue

                self.EXECUTOR.submit(command, file_path)

            if not recursive:
                return

    def _file_extension_matches_filter(self, file: str) -> bool:
        if not self._file_extension_filter:
            return True

        filename, file_extension = os.path.splitext(file)

        if file_extension.lower() not in (ext.lower() for ext in self._file_extension_filter):
            # skip file with unwanted file extension
            return False
        else:
            return True

    def _analyze_file(self, file_path):
        self._progress_bar.set_postfix_str("Analyzing Image '%s' ..." % file_path)

        self._persistence.add(file_path)

        self._increment_progress(1)

    def _remove_duplicates(self, reference_file_path: str, dry_run: bool = True):
        """
        Removes all duplicates of the specified file
        :param reference_file_path: the file to check for duplicates
        :param dry_run: if true, no files will actually be removed
        """

        self._increment_progress(1)

        if self._persistence.get(reference_file_path)[0]['metadata']['already_deduplicated']:
            return
        else:
            self._progress_bar.set_postfix_str("Searching duplicates for '%s' ..." % reference_file_path)

        if not os.path.exists(reference_file_path):
            # remove from persistence
            self._persistence.remove(reference_file_path)
            return

        duplicate_candidates = self._persistence.search_similar(reference_file_path)

        self._progress_bar.set_postfix_str("Removing duplicates for '%s' ..." % reference_file_path)

        reference_file_size = os.stat(reference_file_path).st_size
        reference_file_mod_date = os.path.getmtime(reference_file_path)

        candidates_sorted_by_filesize = sorted(duplicate_candidates, key=lambda c: c['metadata']['filesize'])

        duplicate_files_of_reference_file = []
        for candidate in candidates_sorted_by_filesize:
            candidate_path = candidate['path']
            candidate_dist = candidate['dist']
            candidate_filesize = candidate['metadata']['filesize']
            candidate_modification_date = candidate['metadata']['modification_date']

            # skip candidate if it's the same file
            if candidate_path == reference_file_path:
                continue

            duplicate_files_of_reference_file.append(candidate_path)

            # print("File '%s' is duplicate of '%s' with a dist value of '%s'" % (
            #     reference_file_path, candidate_path, candidate_dist))

            # compare filesize, modification date
            if reference_file_size <= candidate_filesize and \
                    candidate_modification_date <= reference_file_mod_date:

                # remove the smaller/equal sized and/or older/equally old file
                if dry_run:
                    # print("DRY RUN: Would remove '%s'" % candidate_path)
                    pass
                else:
                    # print("Removing '%s'" % candidate_path)
                    # remove from file system
                    os.remove(candidate_path)

                self._deduplication_result.add_removed_file(candidate_path)

                # remove from persistence
                self._persistence.remove(candidate_path)

        self._deduplication_result.set_file_duplicates(reference_file_path, duplicate_files_of_reference_file)

        # remember that this file has been processed in it's current state
        if not dry_run:
            self._persistence.update(reference_file_path, {"already_deduplicated": True})

    def _remove_empty_folders(self, root_path: str, remove_root: bool = True, dry_run: bool = True):
        """
        Function to remove empty folders
        :param root_path:
        :param remove_root:
        :return:
        """
        if not os.path.isdir(root_path):
            return

        # remove empty subfolders
        files = os.listdir(root_path)
        if len(files):
            for f in files:
                fullpath = os.path.join(root_path, f)
                if os.path.isdir(fullpath):
                    self._remove_empty_folders(fullpath, dry_run=dry_run)

        # if folder empty, delete it
        files = os.listdir(root_path)
        if len(files) == 0 and remove_root:

            if dry_run:
                print("DRY RUN: Would remove empty folder '%s'" % root_path)
            else:
                print("Removing empty folder '%s'" % root_path)
                os.rmdir(root_path)

            self._deduplication_result.add_removed_empty_folder(root_path)

    def _update_files_count(self, directory: str, recursive: bool) -> int:
        """
        Count the files in the given directory
        :param directory:
        :return:
        """

        files_count = 0
        for r, d, files in os.walk(directory):
            for file in files:
                if self._file_extension_matches_filter(file):
                    files_count += 1
            if not recursive:
                break

        self._files_count = files_count
        return self._files_count

    def _increment_progress(self, increase_count_by: int = 1):
        self._progress_bar.update(n=increase_count_by)

    def _create_progressbar(self, file_count) -> tqdm:
        if self._progress_bar:
            self._progress_bar.close()

        self._progress_bar = tqdm(total=file_count, unit="Files", unit_scale=True, mininterval=1)
        return self._progress_bar
