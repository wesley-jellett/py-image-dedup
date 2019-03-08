from py_image_dedup.library.DeduplicatorConfig import DeduplicatorConfig
from py_image_dedup.library.ImageMatchDeduplicator import ImageMatchDeduplicator
from py_image_dedup.persistence.ElasticSearchStoreBackend import ElasticSearchStoreBackend

deduplicator = ImageMatchDeduplicator(
    image_signature_store=ElasticSearchStoreBackend(
        host="127.0.0.1",
        # host="192.168.2.24",
        max_dist=0.30,
        use_exif_data=True
    )
)

deduplicatorConfig = DeduplicatorConfig(
    recursive=True,
    search_across_root_directories=True,
    file_extension_filter=[
        ".png",
        ".jpg",
        ".jpeg"
    ],
    # max_file_modification_time_diff=1 * 1000 * 60 * 5,
)

result = deduplicator.deduplicate(
    skip_analyze_phase=False,
    directories=[
        # r'/home/markus/py-image-dedup/dir1',
        # r'/home/markus/py-image-dedup/dir2'
        r'/mnt/data/py-dedup-test/Syncthing'
    ],
    config=deduplicatorConfig,
    threads=8,
    dry_run=True
)

result.print_to_console()
