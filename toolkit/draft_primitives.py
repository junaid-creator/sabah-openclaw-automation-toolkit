"""Source-derived create-once and readback-before-update operations."""
def create_once(run, operation, create, read):
    """Unknown creation never gets a second POST, including after process death."""
    previous = run.data['operations'].get(operation)
    if previous:
        object_id = previous.get('object_id')
        if not object_id:
            raise RuntimeError('REVIEW_REQUIRED: creation outcome lacks a stable ID')
        return read(object_id)
    run.checkpoint(operation, 'sending', attempts=1)
    try:
        result = create()
        object_id = int(result['id'])
        if object_id<=0: raise ValueError('Positive remote ID required')
        run.checkpoint(operation, 'created', attempts=1, object_id=object_id)
    except Exception:
        run.checkpoint(operation, 'review_required', attempts=1)
        raise RuntimeError('REVIEW_REQUIRED: do not retry object creation') from None
    result = read(object_id)
    run.checkpoint(operation, 'verified', attempts=1, object_id=object_id)
    return result

def update_known(run, operation, expected, write, read):
    def reconcile():
        current = read()
        return ('matched' if all(current.get(k) == v for k, v in expected.items())
                else 'absent'), {'verified': current == expected}
    state, _ = reconcile()
    if state == 'matched':
        return
    if run.data['operations'].get(operation, {}).get('state') == 'verified':
        raise RuntimeError('Previously verified values changed; review required')
    run.write(operation, write, reconcile)
    if reconcile()[0] != 'matched':
        raise RuntimeError('Saved-value verification failed')
