'use client';

import { useState } from 'react';
import {
  ArrowUpRight,
  Check,
  Copy,
  Monitor,
  ScanLine,
  Terminal,
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const modes = [
  {
    id: 'desktop',
    icon: Monitor,
    label: 'Desktop',
    file: 'play_gui.py',
    title: 'All the game. Zero setup drama.',
    description:
      'A Pygame board, five AI personalities, and a familiar point-and-click game. No camera required.',
    command: 'python play_gui.py --difficulty hard',
    tag: 'PYGAME GUI',
    hint: 'Choose easy, medium, hard, impossible, or neural.',
  },
  {
    id: 'terminal',
    icon: Terminal,
    label: 'Terminal',
    file: 'play_cli.py',
    title: 'Just you, the board, and a cursor.',
    description:
      'Play directly from your terminal. Add optional voice commentary or turn the challenge up to the exact solver.',
    command: 'pefforza-cli --difficulty impossible',
    tag: 'COMMAND LINE',
    hint: 'Add --voice for optional spoken commentary.',
  },
  {
    id: 'physical',
    icon: ScanLine,
    label: 'Physical board',
    file: 'play_physical.py',
    title: 'Bring your own board.',
    description:
      'Point a webcam at the game, click its four corners, and let computer vision read your next move.',
    command: 'python play_physical.py --difficulty hard',
    tag: 'AUGMENTED REALITY',
    hint: 'SPACE to analyze the position. Q to quit.',
  },
];

export function Launchpad() {
  const [copied, setCopied] = useState('');
  const [copyError, setCopyError] = useState(false);
  async function copy(command: string) {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(command);
      setCopyError(false);
    } catch {
      setCopyError(true);
    }
  }
  return (
    <section id="get-started" className="launch-section section-pad">
      <div className="section-label">
        <span>02 / MAKE IT YOURS</span>
        <span>BUILT IN PYTHON. OPEN TO EVERYONE.</span>
      </div>
      <div className="launch-heading">
        <h2>
          Same intelligence.
          <br />
          <span className="serif">Your kind of play.</span>
        </h2>
        <p>
          Take the experiment off this page.
          <br />
          Clone it. Play it. Make it better.
        </p>
      </div>
      <Tabs defaultValue="desktop" className="launch-tabs">
        <TabsList
          className="launch-tabs-list"
          aria-label="Choose a way to play"
        >
          {modes.map((mode) => (
            <TabsTrigger key={mode.id} value={mode.id} className="launch-tab">
              <mode.icon size={18} />
              {mode.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {modes.map((mode) => (
          <TabsContent key={mode.id} value={mode.id} className="launch-panel">
            <div>
              <span className="chapter-kicker">{mode.tag}</span>
              <h3>{mode.title}</h3>
              <p>{mode.description}</p>
              <span className="launch-hint">{mode.hint}</span>
            </div>
            <div className="terminal-window">
              <div className="terminal-title">
                <span aria-hidden="true">
                  <i />
                  <i />
                  <i />
                </span>
                <span>{mode.file}</span>
                <span>PYTHON 3.10–3.13</span>
              </div>
              <div className="terminal-code">
                <span className="terminal-comment">
                  # In your installed Pefforza checkout
                </span>
                <div>
                  <span className="prompt-char">❯</span>
                  <code>{mode.command}</code>
                </div>
                <span className="terminal-comment">
                  # Your next move starts here
                  <span className="terminal-caret">▌</span>
                </span>
              </div>
              <button
                className="copy-button"
                onClick={() => copy(mode.command)}
                aria-label={`Copy ${mode.label} launch command`}
              >
                {copied === mode.command ? (
                  <Check size={15} />
                ) : (
                  <Copy size={15} />
                )}
                {copied === mode.command ? 'Copied' : 'Copy command'}
              </button>
              <output className="sr-only">
                {copyError
                  ? 'Copy unavailable. Select and copy the command manually.'
                  : copied === mode.command
                    ? 'Command copied to clipboard.'
                    : ''}
              </output>
              {copyError && (
                <p className="copy-error">Select and copy the command above.</p>
              )}
            </div>
          </TabsContent>
        ))}
      </Tabs>
      <div className="launch-bottom">
        <span>
          First time here?{' '}
          <a
            href="https://github.com/tzii/Pefforza_4#quick-start"
            target="_blank"
            rel="noreferrer"
          >
            Follow the installation guide <ArrowUpRight size={14} />
          </a>
        </span>
        <div>
          <span>PYTHON</span>
          <span>OPENCV</span>
          <span>GYMNASIUM</span>
          <span>SB3</span>
        </div>
      </div>
    </section>
  );
}
