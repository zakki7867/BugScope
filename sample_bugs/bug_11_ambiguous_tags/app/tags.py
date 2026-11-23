def process_tags(tags):
    # Ambiguous business policy
    if not tags:
        raise ValueError('Tags cannot be empty')
    return [t.strip().lower() for t in tags]