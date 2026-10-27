# YokTez MCP: YÖK Ulusal Tez Merkezi için MCP Sunucusu


Bu proje, Yükseköğretim Kurulu (YÖK) Ulusal Tez Merkezi'ne erişimi kolaylaştıran bir [FastMCP](https://gofastmcp.com/) sunucusu oluşturur. Bu sayede, YÖK Tez Merkezi'nden tez arama ve tezlerin PDF içeriklerini Markdown formatında getirme işlemleri, Model Context Protocol (MCP) destekleyen LLM (Büyük Dil Modeli) uygulamaları (örneğin Claude Desktop veya [5ire](https://5ire.app)) ve diğer istemciler tarafından araç (tool) olarak kullanılabilir hale gelir.

![YÖK Tez MCP Örneği](./ornek.png)

🎯 **Temel Özellikler**

* YÖK Ulusal Tez Merkezi'ne programatik erişim için standart bir MCP arayüzü.
* Aşağıdaki yetenekler:
    * **Detaylı Tez Arama:** Başlık, yazar, danışman, üniversite, enstitü, anabilim/bilim dalı, tez türü, yıl aralığı, izin durumu, tez numarası, konu, dizin ve özet metni gibi çeşitli kriterlere göre tez arama.
    * **Tez Belgesi Getirme:** Belirli bir tezin PDF içeriğini, PDF sayfa bazında, işlenmiş Markdown formatında getirme.
    * **Metadata Çıkarımı:** Tez detay sayfalarından başlık, yazar, yıl, özet gibi önemli üst verilerin çıkarılması.
    * **PDF İzin Kontrolü:** Erişilemeyen veya yayın izni olmayan tezler için uygun bildirim.
* Karar metinlerinin LLM'ler tarafından daha kolay işlenebilmesi için Markdown formatına çevrilmesi.
* Claude Desktop uygulaması ile `fastmcp install` komutu (veya manuel yapılandırma) kullanılarak kolay entegrasyon.
* YokTez MCP [5ire](https://5ire.app) gibi Claude Desktop haricindeki MCP istemcilerini de destekler.

---

## 🚀 5 Dakikada Başla (Remote MCP)

### ✅ Kurulum Gerektirmez! Hemen Kullan!

🔗 **Remote MCP Adresi:** `https://yoktezmcp.fastmcp.app/mcp`

### Claude Desktop ile Kullanım

1. **Claude Desktop'ı açın**
2. **Settings → Connectors → Add Custom Connector**
3. **Bilgileri girin:**
   - **Name:** `YokTez MCP`
   - **URL:** `https://yoktezmcp.fastmcp.app/mcp`
4. **Add** butonuna tıklayın
5. **Hemen kullanmaya başlayın!** 🎉

### Google Antigravity ile Kullanım

1. **Agent session** açın ve editörün yan panelindeki **"…"** dropdown menüsüne tıklayın
2. **MCP Servers** seçeneğini seçin - MCP Store açılacak
3. Üstteki **Manage MCP Servers** butonuna tıklayın
4. **View raw config** seçeneğine tıklayın
5. `mcp_config.json` dosyasına aşağıdaki yapılandırmayı ekleyin:

```json
{
  "mcpServers": {
    "yoktez-mcp": {
      "serverUrl": "https://yoktezmcp.fastmcp.app/mcp/",
      "headers": {
        "Content-Type": "application/json"
      }
    }
  }
}
```

> 💡 **İpucu:** Remote MCP sayesinde Python, uv veya herhangi bir kurulum yapmadan doğrudan Claude Desktop üzerinden YÖK Ulusal Tez Merkezi'ne erişebilirsiniz!

---

🚀 **Claude Haricindeki Modellerle Kullanmak İçin Çok Kolay Kurulum (Örnek: 5ire için)**

Bu bölüm, YokTez MCP aracını 5ire gibi Claude Desktop dışındaki MCP istemcileriyle kullanmak isteyenler içindir.

* **Python Kurulumu:** Sisteminizde Python 3.11 kurulu olmalıdır. Kurulum sırasında "**Add Python to PATH**" (Python'ı PATH'e ekle) seçeneğini işaretlemeyi unutmayın. [Buradan](https://www.python.org/downloads/) 3.11 sürümünü indirebilirsiniz.
* **Git Kurulumu (Windows):** Bilgisayarınıza [git](https://git-scm.com/downloads/win) yazılımını indirip kurun. "Git for Windows/x64 Setup" seçeneğini indirmelisiniz.
* **`uv` Kurulumu:**
    * **Windows Kullanıcıları (PowerShell):** Bir CMD ekranı açın ve bu kodu çalıştırın: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
    * **Mac/Linux Kullanıcıları (Terminal):** Bir Terminal ekranı açın ve bu kodu çalıştırın: `curl -LsSf https://astral.sh/uv/install.sh | sh`
* **Microsoft Visual C++ Redistributable (Windows):** Bazı Python paketlerinin doğru çalışması için gereklidir. [Buradan](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170) indirip kurun.
* İşletim sisteminize uygun [5ire](https://5ire.app) MCP istemcisini indirip kurun.
* 5ire'ı açın. **Workspace -> Providers** menüsünden kullanmak istediğiniz LLM servisinin API anahtarını girin.
* **Tools** menüsüne girin. **+Local** veya **New** yazan butona basın.
    * **Tool Key:** `yoktezmcp`
    * **Name:** `YokTez MCP`
    * **Command:**
        ```
        uvx --from git+https://github.com/saidsurucu/yoktez-mcp yoktez-mcp
        ```
    * **Save** butonuna basarak kaydedin.

![5ire YokTez MCP Ayarları](./5ire-settings.png)

* Şimdi **Tools** altında **YokTez MCP**'yi görüyor olmalısınız. Üstüne geldiğinizde sağda çıkan butona tıklayıp etkinleştirin (yeşil ışık yanmalı).
* Artık YokTez MCP ile konuşabilirsiniz.

---
⚙️ **Claude Desktop Manuel Kurulumu**


1.  **Ön Gereksinimler:** Python, `uv`, (Windows için) Microsoft Visual C++ Redistributable'ın sisteminizde kurulu olduğundan emin olun. Detaylı bilgi için yukarıdaki "5ire için Kurulum" bölümündeki ilgili adımlara bakabilirsiniz.
2.  Claude Desktop **Settings -> Developer -> Edit Config**.
3.  Açılan `claude_desktop_config.json` dosyasına `mcpServers` altına ekleyin:

    ```json
    {
      "mcpServers": {
        // ... (varsa diğer sunucularınız) ...
        "YokTez MCP": {
          "command": "uvx",
          "args": [
            "--from", "git+https://github.com/saidsurucu/yoktez-mcp",
            "yoktez-mcp"
          ]
        }
      }
    }
    ```

4.  Claude Desktop'ı kapatıp yeniden başlatın.

---

🧩 **MCP Yerine Skill Olarak Kullanım (Claude in Chrome / Claude Desktop tarayıcısı)**

Sunucu kurmak istemeyenler için aynı yetenekler [`skills/yoktez`](./skills/yoktez) klasöründe bir Claude **skill**'i olarak da var. Skill, tarayıcıda açık bir `tez.yok.gov.tr` sekmesine JavaScript enjekte ederek çalışır; Python, `uv` ya da MCP sunucusu gerekmez. YÖK'te CAPTCHA veya giriş zorunluluğu olmadığından hem Claude in Chrome eklentisiyle hem de Claude Desktop'ın yerleşik tarayıcısıyla çalışır.

Skill'in yapabildikleri:

* Anahtar kelimeyle arama (tez adı / yazar / danışman / konu / anahtar kelime / özet; en fazla 3 terim, ve/veya)
* Detaylı arama: Anabilim Dalı kodları (birden fazlası birleştirilir), tez adı, yazar, danışman, anahtar kelime, özet, **tez numarası**, tür, dil, yıl, izin durumu
* Anabilim Dalı adından kod bulma, son eklenen tezler
* Danışman, Türkçe/İngilizce özet, anahtar kelimeler ve hazır atıflar (APA, IEEE, MLA, Chicago, Harvard)
* Tez PDF'ini sayfa aralığıyla metin olarak okuma (yazarın kısıtladığı tezlerde kısıtlama gerekçesini bildirir)

**Kurulum (Claude Code):**

```bash
git clone https://github.com/saidsurucu/yoktez-mcp && cp -r yoktez-mcp/skills/yoktez ~/.claude/skills/
```

**Kurulum (Claude Desktop / claude.ai):** `skills/yoktez` klasörünü zip'leyip **Settings → Capabilities → Skills** bölümünden yükleyin.

Ayrıntılar için [`skills/yoktez/SKILL.md`](./skills/yoktez/SKILL.md) ve [`skills/yoktez/reference.md`](./skills/yoktez/reference.md) dosyalarına bakın.

---

🛠️ **Kullanılabilir Araçlar (MCP Tools)**

Bu FastMCP sunucusu LLM modelleri için aşağıdaki araçları sunar:

* **`search_yok_tez_detailed`**: YÖK Ulusal Tez Merkezi'nde çeşitli detaylı kriterleri kullanarak tez araması yapar.
    * **Parametreler**: `thesis_title`, `author_name`, `advisor_name`, `university_name`, `institute_name`, `department_name`, `discipline_name`, `thesis_number`, `subject_headings`, `index_terms`, `abstract_text`, `thesis_type`, `permission_status`, `thesis_status`, `language`, `institute_group`, `year_start`, `year_end`, `page`, `results_per_page`.
    * **Döndürdüğü Değer**: `YokTezSearchResult` (sayfalanmış tez özeti listesi, toplam sonuç sayısı vb. içerir)

* **`get_yok_tez_document_markdown`**: Belirli bir YÖK tezinin PDF içeriğini, istenen PDF sayfasına göre Markdown formatında getirir.
    * **Parametreler**: `detail_page_url` (tez detay sayfası URL'si), `page_number` (istenen PDF sayfa numarası).
    * **Döndürdüğü Değer**: `YokTezDocumentMarkdown` (sayfanın Markdown içeriği, toplam sayfa sayısı, metadata vb. içerir)

📜 **Lisans**

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakınız.
