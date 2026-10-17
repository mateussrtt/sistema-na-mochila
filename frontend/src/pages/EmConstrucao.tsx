type Props = {
  titulo: string
}

export default function EmConstrucao({ titulo }: Props) {
  return (
    <section>
      <h1>{titulo}</h1>
      <p>Tela em construção.</p>
    </section>
  )
}
