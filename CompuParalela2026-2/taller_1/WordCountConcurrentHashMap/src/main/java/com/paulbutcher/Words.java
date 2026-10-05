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
import java.util.NoSuchElementException;

class Words implements Iterable<String> {

  private final String text;

  public Words(String text) {
    this.text = text;
  }

  /** Un segmento es palabra si contiene al menos una letra o digito. */
  private static boolean isWord(String s) {
    for (int i = 0; i < s.length(); ++i) {
      if (Character.isLetterOrDigit(s.charAt(i)))
        return true;
    }
    return false;
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

    /** Avanza hasta el siguiente segmento que sea una palabra real. */
    private void advance() {
      nextWord = null;
      while (end != BreakIterator.DONE) {
        String s = text.substring(start, end);
        start = end;
        end = wordBoundary.next();
        if (isWord(s)) {
          nextWord = s;
          return;
        }
      }
    }

    public boolean hasNext() { return nextWord != null; }

    public String next() {
      if (nextWord == null)
        throw new NoSuchElementException();
      String result = nextWord;
      advance();
      return result;
    }

    public void remove() { throw new UnsupportedOperationException(); }
  }

  public Iterator<String> iterator() {
    return new WordIterator();
  }
}
