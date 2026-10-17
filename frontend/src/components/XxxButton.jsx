import LabelButton from './LabelButton'

export default function XxxButton({ docId, isXxx: initialXxx }) {
  return <LabelButton key={docId} docId={docId} field="is_xxx" initialValue={initialXxx} />
}
