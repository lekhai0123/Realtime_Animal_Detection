class ClassStats:
    def __init__(self, label_map):
        self.label_map = label_map

    def snapshot(self, class_ids):
        from collections import Counter
        temp = Counter()
        for cid in class_ids:
            name = self.label_map.get(int(cid), "unknown")
            temp[name] += 1
        return dict(temp.most_common(8))
