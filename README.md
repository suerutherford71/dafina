# Dafina

**Your design inspiration, labelled by Claude.**

Dafina gathers the screenshots, downloads and saved pages scattered across your Mac into one private, searchable library. Claude looks at every image and writes its title, labels, colour palette, design brief and a ready-made image prompt, so you can find the right reference in seconds.

Free · Mac only · Website: https://suerutherford71.github.io/dafina/

## Install

Open Terminal (press ⌘ Space, type **Terminal**, press Return), paste this line and press Return:

```bash
curl -fsSL https://raw.githubusercontent.com/suerutherford71/dafina/main/install.sh | bash
```

Dafina is installed in a `Dafina` folder in your home folder and opens in your browser at http://localhost:4610. Next time, double-click **Start Catalogue** in that folder.

If your Mac asks to install "command line developer tools", click Install, wait for it to finish, then paste the line again.

Running the line again updates Dafina. Your images (`sources/`) and labels (`catalogue.json`) are never touched.

## Label your images

1. Add images: click **+ Add** in Dafina, paste a screenshot with ⌘V, or drop images into the folders inside `sources`. Every folder in `sources` is a category; folders inside those are sub-categories.
2. In the Claude desktop app, open the **Code** tab, choose your Dafina folder and type: **label my dafina**

## Save from Chrome and Figma

- **Chrome:** go to `chrome://extensions`, turn on Developer mode, click **Load unpacked** and choose the `chrome-extension` folder in your Dafina folder. Pin **Save to Dafina** from the jigsaw icon.
- **Figma (desktop app):** Plugins › Development › Import plugin from manifest…, then choose `figma-plugin/manifest.json` in your Dafina folder.

## What you need

- A Mac
- Google Chrome (for website screenshots and the extension)
- The Claude desktop app with a paid plan (Pro or above) for labelling
- Optional: the Figma desktop app

## Privacy

Dafina runs entirely on your own Mac and never uploads your images. When you ask Claude to label them, Claude looks at the new images through your own Claude account.

## Licence

Free to use, including for client and commercial work. Please don't sell it or present it as your own. See [LICENCE.txt](LICENCE.txt).

Dafina is an independent project that works with Claude. It isn't made, endorsed or supported by Anthropic.

Made by Sue Rutherford. If Dafina saves you time, you can [buy me a coffee](https://ko-fi.com/YOUR-NAME).
