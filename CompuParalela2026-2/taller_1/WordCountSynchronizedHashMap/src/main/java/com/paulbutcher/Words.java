/***
 * Excerpted from "Seven Concurrency Models in Seven Weeks",
 * published by The Pragmatic Bookshelf.
 * Copyrights apply to this code. It may not be used to create training material, 
 * courses, books, articles, and the like. Contact us if you are in doubt.
 * We make no guarantees that this code is fit for any purpose. 
 * Visit http://www.pragmaticprogrammer.com/titles/pb7con for more book information.
***/
package com.paulbutcher;

import java.text.BreakIterator;
import java.util.Iterator;

class Words implements Iterable<String> {

  private final String text;

  public Words(String text) {
    this.text = text;
  }

  private class WordIterator implements Iterator<String> {

    private BreakIterator wordBoundary;
    private int start;
    private int end;
    private String nextWord;

    public WordIterator() {
      wordBoundary = BreakIterator.getWordInstance();
      wordBoundary.setText(text);
      start = wordBoundary.first();
      end = wordBoundary.next();
      advance();
    }

    // Devuelve true solo para tokens que son palabras reales:
    // al menos 2 caracteres y que contengan alguna letra o digito.
    private boolean isWord(String s) {
      if (s.length() < 2) return false;
      for (int i = 0; i < s.length(); i++) {
        if (Character.isLetterOrDigit(s.charAt(i))) return true;
      }
      return false;
    }

    // Avanza hasta el siguiente token valido (o deja nextWord en null si no hay).
    private void advance() {
      nextWord = null;
      while (end != BreakIterator.DONE) {
        String s = text.substring(start, end);
        start = end;
        end = wordBoundary.next();
        if (isWord(s)) {
          nextWord = s.toLowerCase();
          return;
        }
      }
    }

    public boolean hasNext() { return nextWord != null; }

    public String next() {
      String current = nextWord;
      advance();
      return current;
    }

    public void remove() { throw new UnsupportedOperationException(); }
  }

  public Iterator<String> iterator() {
    return new WordIterator();
  }
}