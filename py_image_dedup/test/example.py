import unittest


class Test(unittest.TestCase):

    def test_analyze(self):
        pass
        # runner = CliRunner()
        # result = runner.invoke(analyze, ['-d D:/test'])
        # assert result.exit_code == 0
        # print(result)

    #    analyze('-d D:/test')

    # def test_analyze(self):
    #     from py_image_dedup.library.Deduplicator import Deduplicator
    #     deduplicator = Deduplicator(['D:/test'])
    #
    #     result = deduplicator.analyze(True)
    #     print(result)

    def test_deduplicate(self):
        from py_image_dedup.library.Deduplicator import Deduplicator
        deduplicator = Deduplicator(['D:/test'])

        result = deduplicator.deduplicate(
            recursive=True,
            file_extensions=[".png", ".jpg", ".jpeg"],
            dry_run=False)

        for r in result:
            print(r)


if __name__ == '__main__':
    unittest.main()
