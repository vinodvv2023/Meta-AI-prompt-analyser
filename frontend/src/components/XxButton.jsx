import LabelButton from './LabelButton'

export default function XxButton({ docId, isXx: initialXx }) {
  return <LabelButton key={docId} docId={docId} field="is_xx" initialValue={initialXx} />
}
