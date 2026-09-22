import type { ReactNode } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

// German-only by decision of the instance owner, so this file is exempt from the
// i18n scan (see scripts/i18n-scan.mjs). Keep it in sync with the code it describes:
// every file path, default and threshold below was checked against the source.

const STAND = '22.09.2026';

const SECTIONS = [
  { id: 'ueberblick', title: 'Überblick und Aufbau' },
  { id: 'kleiderschrank', title: 'Kleiderschrank und Bildanalyse' },
  { id: 'tags', title: 'Tags der Bildanalyse' },
  { id: 'vorschlaege', title: 'Outfit-Vorschläge' },
  { id: 'anlass', title: 'Anlass' },
  { id: 'buttons', title: 'Gefällt mir, Verwerfen, Anderes versuchen' },
  { id: 'kombinationen', title: 'Kombinationen' },
  { id: 'lernen', title: 'Lernprofil' },
  { id: 'regeln', title: 'Körperbereiche und Rollen' },
  { id: 'konfiguration', title: 'Konfiguration und Modelle' },
  { id: 'ausrollen', title: 'Änderungen ausrollen' },
  { id: 'fehlersuche', title: 'Fehlersuche' },
  { id: 'grenzen', title: 'Bekannte Grenzen' },
] as const;

type SectionId = (typeof SECTIONS)[number]['id'];

// Mirrors the VALID_* sets in backend/app/services/ai_service.py and the TYPE list in
// backend/app/prompts/clothing_analysis.txt. The value is what the AI stores and what the
// item detail view shows; the German meaning is for reading only.
const TAG_ROWS: string[][] = [
  [
    'Typ',
    'ja',
    'shirt (Hemd), t-shirt, top, blouse (Bluse), polo, tank-top, sweater (Pullover), hoodie, cardigan (Strickjacke), vest (Weste), jacket (Jacke), blazer, coat (Mantel), pants (Hose), jeans, shorts, skirt (Rock), dress (Kleid), jumpsuit, shoes (Schuhe), sneakers, boots (Stiefel), sandals (Sandalen), socks (Socken), tie (Krawatte), hat (Hut), scarf (Schal), belt (Gürtel), bag (Tasche), accessories',
  ],
  ['Untertyp', 'nein', 'frei, ohne feste Liste. Beispiele: bomber, chinos, chelsea, turtleneck, maxi'],
  [
    'Hauptfarbe, weitere Farben',
    'Hauptfarbe ja',
    'black, white, gray, navy, blue, light-blue, red, burgundy, pink, green, olive, yellow, orange, purple, brown, tan, beige, cream, gold, silver',
  ],
  [
    'Muster',
    'ja',
    'solid (uni), striped (gestreift), plaid (kariert), checkered (kariert, Schachbrett), floral (geblümt), graphic (Print), geometric, polka-dot (gepunktet), camouflage, animal-print',
  ],
  [
    'Material',
    'nein',
    'cotton (Baumwolle), denim, leather (Leder), wool (Wolle), polyester, silk (Seide), linen (Leinen), knit (Strick), fleece, suede (Wildleder), velvet (Samt), nylon, canvas',
  ],
  [
    'Formalität',
    'ja',
    'very-casual (sehr leger), casual (leger), smart-casual, business-casual, formal (formell)',
  ],
  [
    'Stil (1 bis 2)',
    'nein',
    'casual, classic, sporty, minimalist, bohemian, preppy, streetwear, elegant, athletic, vintage, modern, rugged',
  ],
  ['Saison (mehrere)', 'nein', 'spring (Frühling), summer (Sommer), fall (Herbst), winter, all-season (ganzjährig)'],
  ['Passform', 'nein', 'slim, regular, relaxed, oversized, tailored, cropped'],
];

// backend/app/services/item_scorer.py, OCCASION_FORMALITY
const OCCASION_ROWS: string[][] = [
  ['Freizeit', 'casual', 'very-casual, casual, smart-casual'],
  ['Sportlich', 'sporty', 'very-casual, casual'],
  ['Outdoor', 'outdoor', 'very-casual, casual'],
  ['Büro', 'office', 'smart-casual, business-casual, formal'],
  ['Date', 'date', 'smart-casual, business-casual, formal'],
  ['Formell', 'formal', 'business-casual, formal, very-formal'],
];

function Section({ id, description, children }: { id: SectionId; description?: string; children: ReactNode }) {
  const title = SECTIONS.find((s) => s.id === id)?.title;
  return (
    <Card id={id} className="scroll-mt-20">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4 text-sm leading-relaxed">{children}</CardContent>
    </Card>
  );
}

/** Developer detail: where in the code, which setting, which endpoint. */
function Tech({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-2 rounded-md border border-dashed bg-muted/40 p-3 text-xs leading-relaxed">
      <p className="font-semibold uppercase tracking-wide text-muted-foreground">Technisch</p>
      {children}
    </div>
  );
}

function C({ children }: { children: ReactNode }) {
  return <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.8em]">{children}</code>;
}

function Pre({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs leading-relaxed">{children}</pre>
  );
}

function H3({ children }: { children: ReactNode }) {
  return <h3 className="pt-2 text-base font-semibold">{children}</h3>;
}

function List({ children }: { children: ReactNode }) {
  return <ul className="list-disc space-y-1 pl-5">{children}</ul>;
}

function Steps({ children }: { children: ReactNode }) {
  return <ol className="list-decimal space-y-1 pl-5">{children}</ol>;
}

function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-left text-xs">
        <thead className="bg-muted/60">
          <tr>
            {head.map((h) => (
              <th key={h} className="px-3 py-2 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t align-top">
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function HelpPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Hilfe</h1>
        <p className="text-sm text-muted-foreground">
          Was welche Aktion bewirkt, wie die KI arbeitet und wo das im Code steckt. Die grauen
          Kästen „Technisch“ richten sich an die Entwicklung. Stand: {STAND}.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Inhalt</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="grid list-decimal gap-1 pl-5 text-sm sm:grid-cols-2">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a href={`#${s.id}`} className="text-primary underline-offset-4 hover:underline">
                  {s.title}
                </a>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <div className="grid gap-6">
        <Section id="ueberblick" description="Welche Dienste es gibt und wer mit wem spricht.">
          <p>
            Wardrowbe besteht aus mehreren Diensten, die in Docker laufen. Wenn einer davon nicht läuft,
            fallen oft ganz andere Dinge auf als erwartet. Zum Beispiel sieht ein gestoppter Backend-Dienst
            im Browser aus wie ein Netzwerkfehler.
          </p>
          <Table
            head={['Dienst', 'Aufgabe', 'Fällt er aus, dann …']}
            rows={[
              ['frontend', 'Die Oberfläche. Leitet alle Anfragen an das Backend weiter.', 'Die Seite lädt nicht.'],
              ['backend', 'Die API: Kleiderschrank, Outfits, Vorschläge, Kombinationen.', 'Jede Aktion meldet „Unable to reach the backend“.'],
              ['worker', 'Hintergrundjobs: KI-Bildanalyse, Benachrichtigungen, Lernprofil.', 'Neue Teile bleiben ohne Tags hängen.'],
              ['image-worker', 'Bildbearbeitung: Drehen, Hintergrund entfernen.', 'Drehen und Freistellen passieren nicht.'],
              ['postgres', 'Die Datenbank mit allen Daten.', 'Nichts funktioniert.'],
              ['redis', 'Warteschlange für Jobs, Zwischenspeicher, Sperren.', 'Keine Analyse, kein Einreihen von Jobs.'],
              ['ollama', 'Die KI-Modelle, lokal auf dem Server.', 'Analyse und Vorschläge schlagen fehl.'],
            ]}
          />
          <Tech>
            <p>
              Der Browser spricht nie direkt mit dem Backend. Jede Anfrage an <C>/api/v1/…</C> geht durch den
              Proxy in <C>frontend/app/api/v1/[...path]/route.ts</C> zu <C>BACKEND_URL</C> (Standard{' '}
              <C>http://backend:8000</C>). Der Proxy setzt kein eigenes Zeitlimit, es gilt das von Node:
              Kommen nach 5 Minuten keine Antwort-Header, bricht er ab.
            </p>
            <p>
              Die KI wird über eine OpenAI-kompatible Schnittstelle angesprochen (<C>AI_BASE_URL</C>, bei Ollama{' '}
              <C>…:11434/v1</C>). Zuerst werden eigene Endpunkte aus den Nutzer-Einstellungen versucht, der
              Standard-Endpunkt aus der <C>.env</C> hängt immer als Rückfall dahinter (
              <C>backend/app/services/ai_service.py</C>).
            </p>
          </Tech>
        </Section>

        <Section id="kleiderschrank" description="Was beim Hochladen passiert und woher die Tags kommen.">
          <H3>Hochladen</H3>
          <p>
            Nach dem Hochladen wird das Bild im Hintergrund von der KI analysiert. Das Teil erscheint sofort,
            die Tags kommen später dazu. Auf einem Rechner ohne Grafikkarte kann das mehrere Minuten pro Teil
            dauern. Standardmäßig wird immer nur ein Teil gleichzeitig analysiert.
          </p>
          <p>Die Analyse besteht aus zwei getrennten Anfragen an das Bildmodell:</p>
          <Steps>
            <li>
              <strong>Tags:</strong> Typ, Farben, Muster, Material, Formalität, Stil, Saison, Passform. Erlaubt
              sind nur Werte aus festen Listen. Nennt die KI etwas anderes (etwa „aquamarin“), bleibt das Feld
              leer, statt einen erfundenen Wert zu speichern.
            </li>
            <li>
              <strong>Beschreibung:</strong> ein kurzer Satz, der nur zur Anzeige dient. Er fließt nicht in
              Outfit-Vorschläge ein. Ein zu langer Text ist also ein Schönheitsfehler, verschlechtert aber keine
              Vorschläge.
            </li>
          </Steps>

          <H3>Tags von Hand ändern</H3>
          <p>
            Korrigierst du Typ, Untertyp oder Hauptfarbe, gilt das Teil als „manuell getaggt“. Diese Korrektur
            bleibt erhalten, auch wenn du später neu analysieren lässt. Die übrigen Tags lassen sich in der App
            nicht ändern, siehe <a href="#tags" className="text-primary underline-offset-4 hover:underline">Tags der Bildanalyse</a>.
          </p>

          <H3>„Erneut mit KI analysieren“</H3>
          <Table
            head={['Zustand des Teils', 'Was passiert']}
            rows={[
              ['Wird gerade analysiert', 'Nichts. Der laufende Job wird nicht doppelt gestartet.'],
              ['Letzte Analyse ist fehlgeschlagen', 'Erst nach einer Wartezeit von 2 Minuten möglich. Vorher kommt ein Hinweis mit der Restzeit.'],
              ['KI-Bildanalyse ist abgeschaltet', 'Kein Job. Das Teil bleibt „ungetaggt“.'],
              ['Alle anderen Fälle', 'Das Teil wird neu in die Warteschlange gestellt.'],
            ]}
          />
          <p>Bei einer neuen Analyse gilt:</p>
          <List>
            <li>
              <strong>Immer neu:</strong> Beschreibung und die Tag-Übersicht.
            </li>
            <li>
              <strong>Nur wenn leer:</strong> Typ, Farben, Muster, Material, Stil, Formalität, Saison. Von dir
              korrigierte Werte bleiben also stehen.
            </li>
          </List>

          <Tech>
            <p>
              Upload: <C>POST /api/v1/items</C> und <C>/items/bulk</C> in <C>backend/app/api/items.py</C>. Der Job
              heißt <C>tag_item_image</C> (<C>backend/app/workers/tagging.py</C>). Das Bild wird vorher auf
              höchstens 512 px und JPEG-Qualität 85 verkleinert.
            </p>
            <p>
              Prompts: <C>backend/app/prompts/clothing_analysis.txt</C> (Tags, als JSON) und{' '}
              <C>clothing_description.txt</C> (Satz). Die erlaubten Werte stehen als <C>VALID_COLORS</C>,{' '}
              <C>VALID_PATTERNS</C> usw. in <C>ai_service.py</C>.
            </p>
            <p>
              Gespeichert wird doppelt: als Spalten (<C>type</C>, <C>primary_color</C>, …) und als JSON in{' '}
              <C>tags</C>. Manuelle Änderungen per <C>PATCH /items/{'{id}'}</C> setzen <C>tagged_by = manual</C>. Die
              Überschreib-Regeln stehen in <C>tagging.py</C> direkt nach dem Aufruf von{' '}
              <C>analyze_image</C>.
            </p>
            <p>
              „Erneut analysieren“ ist <C>POST /items/{'{id}'}/analyze</C>. Die Wartezeit nach einem Fehler steuert{' '}
              <C>AI_RETRY_COOLDOWN_SECONDS</C> (Standard 120), die Parallelität <C>AI_TAGGING_CONCURRENCY</C>{' '}
              (Standard 1). Ein Job darf höchstens <C>AI_TIMEOUT × AI_MAX_RETRIES + 60</C> Sekunden laufen,
              mindestens aber 10 Minuten.
            </p>
          </Tech>
        </Section>

        <Section id="tags" description="Welche Werte die KI an einem Teil setzen kann.">
          <p>
            Die KI darf nur Werte aus festen Listen vergeben. Nennt sie etwas anderes, bleibt das Feld leer, statt
            einen erfundenen Wert zu speichern. Nur der Untertyp ist frei. In der Detailansicht eines Teils
            erscheinen die Werte englisch, so wie in der rechten Spalte.
          </p>
          <Table head={['Feld', 'Pflicht', 'Mögliche Werte']} rows={TAG_ROWS} />
          <p>
            <strong>Erkennt die KI keinen gültigen Typ,</strong> bekommt das Teil den Typ „unknown“ und wird nie
            für ein Outfit vorgeschlagen, bis du den Typ von Hand setzt.
          </p>

          <H3>Umgedeutete Farbnamen</H3>
          <p>Einige Farbnamen außerhalb der Liste werden übersetzt statt verworfen:</p>
          <Table
            head={['KI nennt', 'gespeichert als']}
            rows={[
              ['grey, light grey, dark grey, charcoal', 'gray'],
              ['off-white, ivory', 'cream'],
              ['wine, maroon', 'burgundy'],
              ['forest green', 'green'],
              ['dark blue', 'navy'],
              ['royal blue', 'blue'],
              ['sky blue, baby blue', 'light-blue'],
              ['camel, khaki', 'tan'],
              ['rust', 'orange'],
              ['coral, rose', 'pink'],
              ['mauve, lavender', 'purple'],
              ['mustard', 'yellow'],
            ]}
          />

          <H3>Was die KI nie setzt</H3>
          <p>
            Marke, Zustand, Anlass und Merkmale gibt es als Felder, die KI füllt sie aber nicht. Die Marke kannst du
            selbst eintragen.
          </p>

          <H3>Was du selbst ändern kannst</H3>
          <List>
            <li>
              <strong>In der App änderbar:</strong> Name, Typ, Untertyp, Hauptfarbe, Marke, Notizen, Favorit,
              Waschintervall.
            </li>
            <li>
              <strong>Nicht änderbar:</strong> Formalität, Muster, Material, Stil, Saison, Passform und weitere
              Farben. Auch „Erneut mit KI analysieren“ hilft hier nur bei leeren Feldern, einen vorhandenen Wert
              überschreibt es nicht.
            </li>
          </List>
          <p>
            Eine falsch erkannte Formalität wirkt sich direkt auf die Vorschläge aus, siehe{' '}
            <a href="#anlass" className="text-primary underline-offset-4 hover:underline">Anlass</a>. Ändern lässt sie
            sich derzeit nur direkt in der Datenbank.
          </p>

          <Tech>
            <p>
              Listen: <C>VALID_TYPES</C>, <C>VALID_COLORS</C>, <C>VALID_PATTERNS</C>, <C>VALID_MATERIALS</C>,{' '}
              <C>VALID_FORMALITY</C>, <C>VALID_STYLES</C>, <C>VALID_SEASONS</C>, <C>VALID_FIT</C> in{' '}
              <C>backend/app/services/ai_service.py</C>; die Umdeutungen sind <C>COLOR_ALIASES</C> in{' '}
              <C>_parse_tags_from_response</C>. Der Prompt <C>clothing_analysis.txt</C> nennt dieselben Werte.
            </p>
            <p>
              <C>ai_confidence</C> ist keine Sicherheit des Modells, sondern die Vollständigkeit: Typ 25 %,
              Hauptfarbe 20 %, Muster und Formalität je 15 %, Material 10 %, Saison, Stil und weitere Farben je 5 %
              (<C>compute_tag_completeness</C>). Die Anzeige „sicher zu … %“ kommt dagegen aus den
              Token-Wahrscheinlichkeiten und erscheint nur, wenn das Modell sie liefert.
            </p>
            <p>Formalität eines Teils in der Datenbank ändern, Spalte und Anzeige zugleich:</p>
            <Pre>{`SELECT id, name, type, formality FROM clothing_items WHERE name ILIKE '%blazer%';

UPDATE clothing_items
SET formality = 'business-casual',
    tags = jsonb_set(coalesce(tags, '{}'::jsonb), '{formality}', '"business-casual"')
WHERE id = 'ID-DES-TEILS';`}</Pre>
            <p>
              Nicht über <C>PATCH /api/v1/items/{'{id}'}</C> mit <C>tags</C>: Das ersetzt das ganze Tag-Feld durch
              das Geschickte und setzt dabei Farben, Stil und Saison auf leer, wenn sie fehlen (
              <C>ItemService.update</C> in <C>backend/app/services/item_service.py</C>).
            </p>
          </Tech>
        </Section>

        <Section id="vorschlaege" description="Von der Anfrage bis zum fertigen Outfit.">
          <p>
            Pro Anfrage entsteht ein Outfit. Die KI wird dafür zweimal befragt: einmal, um die Teile
            auszuwählen, und einmal, um genau diese Teile zu beschreiben. So kann der Text nie ein Kleidungsstück
            erwähnen, das gar nicht im Outfit ist.
          </p>
          <Steps>
            <li>
              <strong>Kandidaten sammeln:</strong> alle fertig analysierten, nicht archivierten Teile. Raus
              fallen Teile ohne erkannten Typ, Teile, die du in den Einstellungen ausgeschlossen hast, und Teile
              aus heute für diesen Anlass verworfenen Outfits. Ein vorgegebenes Teil kommt immer mit.
            </li>
            <li>
              <strong>Bewerten und sortieren:</strong> nach Wetter, Anlass, deinen Vorlieben, dem Lernprofil,
              bewährten Kombinationen und wann du das Teil zuletzt getragen hast. Nummer 1 passt am besten.
            </li>
            <li>
              <strong>Auswahl:</strong> Die KI bekommt die sortierte Liste und antwortet nur mit Nummern.
            </li>
            <li>
              <strong>Aufräumen:</strong> Nummern, die es nicht gibt, fallen weg. Doppelt belegte Körperbereiche
              werden bereinigt, siehe <a href="#regeln" className="text-primary underline-offset-4 hover:underline">Körperbereiche und Rollen</a>.
            </li>
            <li>
              <strong>Ergänzen:</strong> Fehlt ein ganzer Bereich (kein Oberteil, kein Unterteil oder keine
              Schuhe), kommt das bestplatzierte passende Teil aus der Liste dazu. Das wählt der Code nach
              Rangliste, nicht die KI nach Stil.
            </li>
            <li>
              <strong>Beschreibung:</strong> Die KI bekommt nur die endgültigen Teile und schreibt Titel,
              Highlights und Tipp. Schlägt das fehl, wird das Outfit trotzdem gespeichert, dann eben ohne Text,
              als „Dein Outfit“.
            </li>
          </Steps>
          <p>
            Das Ganze läuft, während der Browser auf die Antwort wartet. Dauert es länger als 5 Minuten, meldet
            die Seite einen Fehler, obwohl der Server im Hintergrund weiterrechnet.
          </p>
          <Tech>
            <p>
              Kandidaten: <C>get_candidate_items</C>. Ist <C>WASH_TRACKING_ENABLED</C> an, fallen auch Teile raus,
              die gewaschen werden müssen.
            </p>
            <p>
              Endpunkt <C>POST /api/v1/outfits/suggest-options</C> mit <C>count=1</C> (
              <C>backend/app/api/outfits.py</C>). Ablauf in <C>generate_recommendations</C> und{' '}
              <C>_materialize_outfit</C> in <C>backend/app/services/recommendation_service.py</C>; das Ergänzen
              ist <C>_fill_empty_regions</C>.
            </p>
            <p>
              Prompts: <C>recommendation.txt</C> (Auswahl, nur Nummern) und <C>outfit_explanation.txt</C>{' '}
              (Beschreibung). Die Beschreibung erzeugt <C>backend/app/services/outfit_explanation.py</C>; Text,
              den die Auswahl trotzdem mitschickt, verwirft <C>strip_explanation</C>. Bewertung:{' '}
              <C>backend/app/services/item_scorer.py</C>.
            </p>
            <p>
              Der Tagesvorschlag per Benachrichtigung nutzt denselben Weg mit <C>single_outfit=True</C>; dort
              ersetzt <C>SINGLE_OUTFIT_FORMAT</C> das Ausgabeformat im Prompt.
            </p>
          </Tech>
        </Section>

        <Section id="anlass" description="Wie der gewählte Anlass die Auswahl beeinflusst.">
          <p>
            Der Anlass bestimmt vor allem, wie formell die Teile sein sollen. Er schließt kein Teil aus, schiebt
            unpassende aber in der Rangliste weit nach hinten.
          </p>
          <Table head={['Anlass in der App', 'Wert', 'Passende Formalität']} rows={OCCASION_ROWS} />
          <p>Jedes Teil bekommt einen Faktor, je nachdem wie gut seine Formalität passt:</p>
          <Table
            head={['Formalität des Teils', 'Faktor']}
            rows={[
              ['passt zum Anlass', '1,0'],
              ['eine Stufe daneben', '0,5'],
              ['weiter daneben', '0,15'],
            ]}
          />
          <p>
            Die Stufen in Reihenfolge: very-casual, casual, smart-casual, business-casual, formal, very-formal. Der
            Faktor wird mit den übrigen Bewertungen <strong>multipliziert</strong>: Wetter, Jahreszeit, wann zuletzt
            getragen, deine Vorlieben, wie oft getragen. Ein legeres T-Shirt beim Anlass Formell liegt zwei Stufen
            neben business-casual und behält nur 15 % seines Werts. Die KI könnte es trotzdem wählen, es steht aber
            ganz unten in ihrer Liste.
          </p>
          <p>
            <strong>Teile ohne Formalität zählen als leger.</strong> Bei Freizeit schadet das nicht, bei Büro oder
            Formell rutschen sie nach hinten.
          </p>
          <H3>Außerdem wirkt der Anlass auf</H3>
          <List>
            <li>
              <strong>die KI:</strong> Sie bekommt den Anlass im Auswahl-Prompt und bei der Beschreibung genannt.
            </li>
            <li>
              <strong>das Lernprofil:</strong> Farbvorlieben werden je Anlass getrennt gelernt, etwa „bei Büro
              bevorzugst du navy, grau“, und der KI mitgeteilt. Hat ein Anlass eine schlechte Trefferquote, erfährt
              sie das auch.
            </li>
            <li>
              <strong>die Sperre beim Verwerfen:</strong> Sie gilt nur für denselben Anlass. Bei einem anderen
              Anlass sind die Teile sofort wieder verfügbar.
            </li>
          </List>
          <p>Wählst du keinen Anlass, gilt der aus deinen Einstellungen, sonst Freizeit.</p>
          <Tech>
            <p>
              <C>OCCASION_FORMALITY</C>, <C>FORMALITY_ORDER</C> und <C>_formality_score</C> in{' '}
              <C>backend/app/services/item_scorer.py</C>; die Multiplikation steht in <C>score_items</C>. Die
              Tabelle kennt auch <C>work</C> und <C>party</C>, die die App nicht anbietet. Unbekannte Anlässe
              behandelt sie wie casual und smart-casual. Anlassbezogene Lernwerte: <C>_get_learned_preferences</C>{' '}
              und <C>_format_preferences_for_prompt</C> in <C>recommendation_service.py</C>.
            </p>
          </Tech>
        </Section>

        <Section id="buttons" description="Die drei Knöpfe unter einem Vorschlag wirken sehr unterschiedlich.">
          <Table
            head={['Knopf', 'Teile heute gesperrt', 'Lernsignal', 'Danach']}
            rows={[
              ['„Gefällt mir“ / „Diesen Look wählen“', 'nein', '+0,3 (positiv)', 'Outfit gilt als deins für heute'],
              ['X / „Outfit verwerfen“', 'ja, alle Teile des Outfits für diesen Anlass', '−0,5 (negativ)', 'Neue Generierung startet sofort'],
              ['„Anderes versuchen“', 'nein', 'keins', 'Neue Generierung'],
            ]}
          />
          <p>
            <strong>Faustregel:</strong> Verwerfen, wenn dir der Look nicht gefällt. „Anderes versuchen“, wenn die
            KI Unbrauchbares geliefert hat. Verwerfen bringt dem System bei, dass dir diese Farben und Stile nicht
            gefallen, auch wenn in Wahrheit die KI danebenlag.
          </p>
          <List>
            <li>
              <strong>Gefällt mir</strong> zählt die Teile nicht als getragen. „Getragen“ ist eine eigene
              Rückmeldung.
            </li>
            <li>
              <strong>Verwerfen</strong> sperrt die Teile bis morgen. Bei einem kleinen Kleiderschrank gehen dir
              nach mehrmaligem Verwerfen die Kandidaten aus, dann meldet die Generierung „nicht genug Teile“. Die
              automatisch folgende Generierung kostet auf einem Rechner ohne Grafikkarte wieder einige Minuten.
            </li>
          </List>
          <Tech>
            <p>
              <C>POST /outfits/{'{id}'}/accept</C> setzt <C>accepted</C>. <C>/reject</C> setzt <C>rejected</C>{' '}
              und leert den Vorschlags-Zwischenspeicher. „Anderes versuchen“ ruft <C>/skip</C> auf und setzt{' '}
              <C>skipped</C>; das zählt weder fürs Lernen noch für die Sperre.
            </p>
            <p>
              Die Sperre ist <C>_get_today_rejected_item_ids</C> in <C>recommendation_service.py</C>. Den Neustart
              nach dem Verwerfen löst <C>handleReject</C> in <C>frontend/app/dashboard/suggest/page.tsx</C> aus,
              sobald kein Vorschlag mehr übrig ist.
            </p>
          </Tech>
        </Section>

        <Section id="kombinationen" description="Passende Outfits rund um ein bestimmtes Teil.">
          <p>
            Du wählst ein Teil und die Anzahl der Outfits. Die KI stellt dazu Kombinationen zusammen, die dieses
            Teil immer enthalten. Die Beschreibung erklärt, warum die übrigen Teile zu deinem Ausgangsteil passen.
          </p>
          <p>
            Unvollständige Kombinationen werden <strong>verworfen, nicht ergänzt</strong>. Anders als bei den
            Vorschlägen sind die Teile hier nicht nach Eignung sortiert, ein Ergänzen würde also ein beliebiges
            Teil nehmen. Du bekommst dann eine Warnung, zum Beispiel „1 unvollständiges Outfit wurde verworfen“.
            Wurde alles verworfen, erscheint eine Fehlermeldung, und du bleibst im Formular, um es erneut zu
            versuchen.
          </p>
          <p>
            Verlangt wird nur, was dein Kleiderschrank hergibt: Hast du keine Schuhe erfasst, gilt eine
            Kombination auch ohne Schuhe als vollständig.
          </p>
          <Tech>
            <p>
              <C>POST /api/v1/pairings/generate/{'{item_id}'}</C> in <C>backend/app/api/pairings.py</C>; Antwort
              enthält <C>generated</C> und <C>discarded</C>. Logik in{' '}
              <C>backend/app/services/pairing_service.py</C>, Prompt <C>item_pairing.txt</C>. Jede Kombination
              bekommt einen eigenen Beschreibungsaufruf. Anzeige im Dialog{' '}
              <C>frontend/components/generate-pairings-dialog.tsx</C>.
            </p>
          </Tech>
        </Section>

        <Section id="lernen" description="Wie deine Rückmeldungen künftige Vorschläge beeinflussen.">
          <p>
            Aus angenommenen und verworfenen Outfits sowie deinen Bewertungen lernt Wardrowbe, welche Farben,
            Stile und Kombinationen du magst, auch je nach Anlass und Wetter. Das fließt in die Rangliste ein, aus
            der die KI auswählt.
          </p>
          <p>
            Das Profil wird <strong>einmal pro Stunde</strong> neu berechnet, jeweils zur halben Stunde. Eine
            Rückmeldung wirkt sich also erst danach auf die Bewertung aus. Die Sperre verworfener Teile gilt
            dagegen sofort.
          </p>
          <Table
            head={['Rückmeldung', 'Wirkung auf das Signal']}
            rows={[
              ['Angenommen', '+0,3'],
              ['Verworfen', '−0,5'],
              ['Bewertung 1 bis 5 Sterne', '−0,4 bis +0,4'],
              ['Als getragen gemeldet', '+0,3'],
              ['… mit Änderungen getragen', '−0,1'],
              ['Ausdrücklich nicht getragen', '−0,4'],
              ['Übersprungen („Anderes versuchen“)', 'keine'],
            ]}
          />
          <H3>„Lernprofil zurücksetzen“</H3>
          <p>
            Der Knopf auf der Seite KI-Lernprofil löscht alle Bewertungen, Getragen-Rückmeldungen und alles
            daraus Gelernte, auch die Paar-Wertungen, die „Neu berechnen“ nicht anfasst. Verworfene Outfits
            werden zu übersprungenen: Sie bleiben im Verlauf, sperren aber keine Teile mehr. Erhalten bleiben
            angenommene Outfits und wie oft deine Teile getragen wurden. Das lässt sich nicht rückgängig machen.
          </p>
          <Tech>
            <p>
              <C>backend/app/services/learning_service.py</C>, Signal in <C>_get_outfit_signal</C>. Der Cron-Job{' '}
              <C>update_learning_profiles</C> läuft im <C>worker</C> zur Minute 30 (
              <C>backend/app/workers/worker.py</C>). Berücksichtigt werden nur Outfits mit Status{' '}
              <C>accepted</C> oder <C>rejected</C>. Der Job rechnet nur für Nutzer neu, die kürzlich eine
              Rückmeldung gegeben haben.
            </p>
            <p>
              <C>item_pair_scores</C> und <C>outfit_performances</C> werden bei jeder Rückmeldung einzeln
              fortgeschrieben (<C>process_feedback</C>) und von <C>recompute_learning_profile</C> nie neu
              aufgebaut. Zurücksetzen: <C>POST /api/v1/learning/reset</C>, Logik in <C>reset_learning</C>.
            </p>
          </Tech>
        </Section>

        <Section id="regeln" description="Die festen Regeln, nach denen der Code ein Outfit bereinigt und ergänzt.">
          <p>Jeder Kleidungstyp hat eine Rolle. Pro Rolle ist ein Teil erlaubt, Accessoires beliebig viele.</p>
          <Table
            head={['Rolle', 'Typen']}
            rows={[
              ['Oberteil', 'shirt, t-shirt, blouse, polo, tank-top, top, sweater'],
              ['Zwischenschicht', 'cardigan, vest'],
              ['Jacke', 'jacket, blazer, coat, hoodie'],
              ['Unterteil', 'pants, jeans, shorts, skirt'],
              ['Ganzkörper', 'dress, jumpsuit'],
              ['Schuhe', 'shoes, sneakers, boots, sandals'],
              ['Socken', 'socks'],
              ['Krawatte', 'tie'],
              ['Accessoire', 'hat, scarf, belt, bag, accessories'],
            ]}
          />
          <H3>Bereinigen</H3>
          <List>
            <li>Zweites Teil einer Rolle (etwa zwei Paar Schuhe) → wird entfernt.</li>
            <li>
              Ein Kleid oder Jumpsuit → <strong>alle</strong> Oberteile und Unterteile werden entfernt, egal an
              welcher Stelle das Kleid gewählt wurde.
            </li>
          </List>
          <H3>Ergänzen (nur Outfit-Vorschläge)</H3>
          <Table
            head={['Bereich', 'Gilt als abgedeckt durch', 'Ergänzt wird']}
            rows={[
              ['Oben', 'Oberteil, Zwischenschicht, Jacke oder Kleid', 'bestes Oberteil'],
              ['Unten', 'Unterteil oder Kleid', 'bestes Unterteil'],
              ['Füße', 'Schuhe', 'beste Schuhe'],
            ]}
          />
          <p>
            Hoodie + Jeans + Sneakers bleibt so, wie es ist: Der Hoodie zählt als Jacke, deckt aber „oben“ ab.
          </p>
          <Tech>
            <p>
              <C>ITEM_ROLE</C>, <C>BODY_REGIONS</C>, <C>missing_body_regions</C> und{' '}
              <C>deduplicate_by_body_slot</C> in <C>backend/app/utils/clothing.py</C>. Jede Entfernung und jede
              Ergänzung erscheint als Warnung im Backend-Log.
            </p>
          </Tech>
        </Section>

        <Section id="konfiguration" description="Die Stellschrauben in der .env und was sie bewirken.">
          <p>
            Die <C>.env</C> liegt nur auf dem Server und ist nicht in Git. Neue Einstellungen musst du dort von
            Hand nachtragen.
          </p>
          <Table
            head={['Variable', 'Standard', 'Bewirkt']}
            rows={[
              [<C key="v">AI_BASE_URL</C>, '–', 'Adresse der KI-Schnittstelle, bei Ollama …:11434/v1'],
              [<C key="v">AI_VISION_MODEL</C>, 'gpt-4o', 'Modell für die Bildanalyse (Tags und Beschreibung)'],
              [<C key="v">AI_TEXT_MODEL</C>, 'gpt-4o', 'Modell für Vorschläge, Kombinationen und Beschreibungen'],
              [<C key="v">AI_TIMEOUT</C>, '120 s', 'Wartezeit auf eine einzelne KI-Antwort'],
              [<C key="v">AI_MAX_RETRIES</C>, '3', 'Wiederholungen pro Endpunkt bei Fehlern'],
              [<C key="v">AI_MAX_TOKENS</C>, '8000', 'Obergrenze für die Länge einer KI-Antwort'],
              [<C key="v">AI_TAGGING_CONCURRENCY</C>, '1', 'Wie viele Bilder gleichzeitig analysiert werden'],
              [<C key="v">AI_RETRY_COOLDOWN_SECONDS</C>, '120', 'Wartezeit, bevor ein fehlgeschlagenes Teil neu analysiert werden darf'],
              [<C key="v">AI_REASONING_EFFORT</C>, 'none', 'Denkaufwand für Modelle, die das unterstützen'],
            ]}
          />
          <H3>Modellwahl</H3>
          <p>
            Ohne Grafikkarte ist die Rechenzeit die harte Grenze. Das Textmodell muss eine Auswahl und eine
            Beschreibung in unter 5 Minuten schaffen, sonst bricht die Seite ab. Größere Modelle halten sich
            besser an die Regeln, sind aber langsamer. Kleinere sind schneller und vergessen eher ein Teil, das
            dann der Code ergänzt.
          </p>
          <Tech>
            <p>
              Standardwerte in <C>backend/app/config.py</C>, Weitergabe an die Container in{' '}
              <C>docker-compose.yml</C>. <C>OLLAMA_KEEP_ALIVE</C> gehört zum <C>ollama</C>-Dienst und legt fest,
              wie lange ein Modell im Speicher bleibt. Die App kann das nicht selbst setzen, weil die
              OpenAI-kompatible Schnittstelle den Parameter nicht kennt.
            </p>
            <p>
              Die Prompts liegen in <C>backend/app/prompts/</C> und werden beim Start des Backends geladen. Sie
              stecken im Image, eine Änderung braucht also einen Neubau des Backends.
            </p>
          </Tech>
        </Section>

        <Section id="ausrollen" description="Was nach welcher Änderung nötig ist.">
          <Table
            head={['Geändert', 'Nötig']}
            rows={[
              ['Wert in der .env', <C key="c">docker compose up -d backend worker</C>],
              ['Python-Code oder Prompt', <C key="c">docker compose build backend</C>],
              ['Frontend-Code oder Übersetzung', <C key="c">docker compose build frontend</C>],
              ['Neue Datenbank-Migration', 'Migration ausführen, siehe unten'],
              ['Einstellung von Ollama', <C key="c">docker compose up -d ollama</C>],
            ]}
          />
          <p>
            <strong>Immer <C>up -d</C>, nie <C>restart</C>.</strong> <C>restart</C> startet den Container mit
            seiner alten Umgebung neu, eine geänderte <C>.env</C> käme nicht an. Der Frontend-Build ist auf dem
            Server der langsame Teil, baue ihn nur, wenn sich dort etwas geändert hat.
          </p>
          <H3>Ablauf auf dem Server</H3>
          <Pre>{`cd ~/wardrowbe
docker compose exec -T postgres pg_dump -U wardrobe wardrobe > ~/wardrobe-$(date +%F).sql
git pull
docker compose build backend            # und/oder frontend
docker compose run --rm backend alembic upgrade head
docker compose up -d
docker compose ps`}</Pre>
          <p>
            Die Migration läuft in einem Wegwerf-Container, solange die alte Version noch weiterläuft. Das
            funktioniert, solange eine Migration nur Spalten hinzufügt, die leer bleiben dürfen. Migrationen
            laufen nicht automatisch beim Start.
          </p>
          <Tech>
            <p>
              Server-spezifische Abweichungen (eigene Image-Namen, der <C>ollama</C>-Dienst) gehören in eine{' '}
              <C>docker-compose.override.yml</C>, die Compose automatisch dazulädt. Damit sie nicht mit{' '}
              <C>git pull</C> kollidiert, trägst du sie in <C>.git/info/exclude</C> ein, nicht in die{' '}
              <C>.gitignore</C>: Die ist selbst versioniert, eine Änderung daran führt beim nächsten Pull zu einem
              Konflikt.
            </p>
          </Tech>
        </Section>

        <Section id="fehlersuche" description="Symptom, wahrscheinliche Ursache, was du prüfst.">
          <p>
            <strong>Zuerst immer:</strong> <C>docker compose ps</C>. Ein gestoppter Dienst erklärt die meisten
            rätselhaften Fehler.
          </p>
          <Table
            head={['Symptom', 'Wahrscheinliche Ursache', 'Prüfen']}
            rows={[
              ['„Unable to reach the backend … (fetch failed)“ sofort', 'Backend läuft nicht', 'docker compose ps, dann docker compose up -d'],
              ['Dieselbe Meldung nach genau 5 Minuten', 'KI ist zu langsam für das Zeitlimit des Proxys', 'Kleineres Textmodell wählen'],
              ['Neue Teile bekommen keine Tags', 'worker oder ollama läuft nicht, oder die Bildanalyse ist abgeschaltet', 'docker compose ps; docker compose exec ollama ollama ps'],
              ['„Erneut analysieren“ meldet eine Wartezeit', 'Die letzte Analyse ist fehlgeschlagen, Sperre von 2 Minuten', 'Kurz warten'],
              ['„Nicht genug Teile“ bei Vorschlägen', 'Heute zu viel verworfen, die Teile sind bis morgen gesperrt', 'Anderen Anlass wählen oder bis morgen warten'],
              ['Einem Outfit fehlt ein Bereich', 'Im Kleiderschrank gibt es kein Teil dieser Rolle', 'Kleiderschrank prüfen'],
              ['Ein Teil taucht nie in Vorschlägen auf', 'Kein erkannter Typ (Analyse fehlgeschlagen), archiviert, in den Einstellungen ausgeschlossen oder heute verworfen', 'Typ von Hand setzen oder „Erneut mit KI analysieren“'],
              ['Im Log fehlen Zeilen wie „Generating recommendation“', 'Info-Meldungen werden gar nicht ausgegeben', 'Siehe Protokolle'],
            ]}
          />
          <H3>Protokolle</H3>
          <p>
            Vom Backend-Code erscheinen im Log nur Warnungen und Fehler. Alle Info-Meldungen fehlen, weil das
            Logging nicht eingerichtet ist. Wenn eine Meldung nicht auftaucht, heißt das also nicht, dass der Code
            nicht lief. Sichtbar sind die Zugriffszeilen des Webservers, damit lässt sich die Dauer einer Anfrage
            messen:
          </p>
          <Pre>{`# Wann ist eine Anfrage fertig? (Zeile erscheint erst am Ende)
docker compose logs -f --tail 0 backend | grep -E "suggest-options|pairings/generate"

# Was hat der Code an einem Outfit korrigiert?
docker compose logs --since 30m backend | grep -E "Removing|added best-ranked|invalid item number|discarding"

# Welche Modelle sind geladen, auf CPU oder GPU?
docker compose exec ollama ollama ps`}</Pre>
          <Tech>
            <p>
              Tests im Backend brauchen Postgres und Redis und die Variable <C>TEST_DATABASE_URL</C> (gesetzt in{' '}
              <C>docker-compose.dev.yml</C>). Die Frontend-Tests brauchen Node 24; mit älterem Node bricht{' '}
              <C>vitest</C> beim Start ab. Ohne passendes Node auf dem Rechner:
            </p>
            <Pre>{`docker run --rm -v "$PWD/frontend:/app" -w /app node:24-slim npx vitest run`}</Pre>
            <p>
              Die CI prüft zusätzlich <C>ruff check</C>, <C>ruff format --check</C>, <C>npm run lint</C>,{' '}
              <C>tsc --noEmit</C>, <C>npm run i18n:check</C> und den Build.
            </p>
          </Tech>
        </Section>

        <Section id="grenzen" description="Was die App derzeit nicht oder nur eingeschränkt kann.">
          <List>
            <li>
              <strong>Vorschläge laufen im Browser-Request.</strong> Es gibt keine Fortschrittsanzeige wie beim
              Kleiderschrank, und nach 5 Minuten bricht die Seite ab. Eine Umstellung auf einen Hintergrundjob
              würde beides lösen.
            </li>
            <li>
              <strong>Info-Protokolle sind unsichtbar.</strong> Das Backend richtet kein Logging ein. Die Variable{' '}
              <C>LOG_LEVEL</C> wird zwar an den image-worker übergeben, aber nirgends ausgewertet.
            </li>
            <li>
              <strong>T-Shirt unter Pullover geht nicht.</strong> Beide sind „Oberteil“, eins wird entfernt.
              Ebenso Hoodie plus Jacke.
            </li>
            <li>
              <strong>Formalität, Muster, Material, Stil, Saison und Passform lassen sich nicht bearbeiten.</strong>{' '}
              Die App bietet dafür kein Feld, und neu analysieren überschreibt vorhandene Werte nicht.
            </li>
            <li>
              <strong>Die Auswahllisten der App passen nicht zu den KI-Werten.</strong> Die App kennt Farben wie
              Khaki, Petrol, Anthrazit, Dunkelbraun und Olivgrün, die die KI nie vergibt. Hellblau, Gold und Silber
              vergibt die KI, sie fehlen aber in der App. Von den 12 KI-Stilen haben nur 3 einen deutschen Namen,
              und „ganzjährig“ fehlt bei den Saisons.
            </li>
            <li>
              <strong>Den Typ Anzug</strong> kannst nur du vergeben, nicht die KI. Er hat keine Rolle und deckt
              deshalb keinen Körperbereich ab: Ein Outfit mit Anzug bekommt trotzdem ein Oberteil und ein Unterteil
              ergänzt.
            </li>
            <li>
              <strong>Kombinationen werden nicht ergänzt.</strong> Die Kandidaten sind dort nicht nach Eignung
              sortiert, deshalb wird verworfen statt aufgefüllt.
            </li>
            <li>
              <strong>Diese Hilfe gibt es nur auf Deutsch.</strong> In anderen Sprachen erscheint ebenfalls dieser
              Text.
            </li>
          </List>
        </Section>
      </div>
    </div>
  );
}
